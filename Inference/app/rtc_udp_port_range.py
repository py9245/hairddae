from __future__ import annotations

import asyncio
import ipaddress
import logging
import random
import socket
from collections.abc import Callable
from typing import Any


logger = logging.getLogger(__name__)


def _create_udp_socket(address: str, port: int) -> socket.socket:
    family = socket.AF_INET6 if ipaddress.ip_address(address).version == 6 else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_DGRAM)
    sock.setblocking(False)
    if family == socket.AF_INET6:
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
    sock.bind((address, port))
    return sock


async def _create_datagram_endpoint_in_range(
    loop: asyncio.AbstractEventLoop,
    protocol_factory: Callable[[], Any],
    address: str,
    min_port: int,
    max_port: int,
) -> tuple[asyncio.DatagramTransport, Any]:
    ports = list(range(min_port, max_port + 1))
    random.shuffle(ports)
    last_error: OSError | None = None

    for port in ports:
        sock: socket.socket | None = None
        try:
            sock = _create_udp_socket(address, port)
            transport, protocol = await loop.create_datagram_endpoint(
                protocol_factory,
                sock=sock,
            )
            return transport, protocol
        except OSError as exc:
            last_error = exc
            if sock is not None:
                sock.close()

    if last_error is None:
        raise OSError(f"could not bind udp socket in configured range {min_port}-{max_port}")
    raise last_error


def configure_aioice_udp_port_range(min_port: int, max_port: int) -> None:
    if min_port <= 0 or max_port <= 0 or min_port > max_port:
        logger.warning(
            "skip aioice udp port range patch because range is invalid: %s-%s",
            min_port,
            max_port,
        )
        return

    import aioice.ice as ice

    current_range = getattr(ice, "_hairddae_udp_port_range", None)
    if current_range == (min_port, max_port):
        return

    if getattr(ice, "_hairddae_original_get_component_candidates", None) is None:
        ice._hairddae_original_get_component_candidates = ice.Connection.get_component_candidates

    async def get_component_candidates_in_range(
        self,
        component: int,
        addresses: list[str],
        timeout: int = 5,
    ) -> list[Any]:
        candidates = []
        loop = asyncio.get_event_loop()

        host_protocols = []
        for address in addresses:
            try:
                transport, protocol = await _create_datagram_endpoint_in_range(
                    loop,
                    lambda: ice.StunProtocol(self),
                    address,
                    min_port,
                    max_port,
                )
                sock = transport.get_extra_info("socket")
                if sock is not None:
                    sock.setsockopt(
                        socket.SOL_SOCKET,
                        socket.SO_RCVBUF,
                        ice.turn.UDP_SOCKET_BUFFER_SIZE,
                    )
            except OSError as exc:
                log_info = getattr(self, "_Connection__log_info", None)
                if callable(log_info):
                    log_info(
                        "Could not bind to %s in %s-%s - %s",
                        address,
                        min_port,
                        max_port,
                        exc,
                    )
                continue

            host_protocols.append(protocol)
            candidate_address = protocol.transport.get_extra_info("sockname")
            protocol.local_candidate = ice.Candidate(
                foundation=ice.candidate_foundation("host", "udp", candidate_address[0]),
                component=component,
                transport="udp",
                priority=ice.candidate_priority(component, "host"),
                host=candidate_address[0],
                port=candidate_address[1],
                type="host",
            )
            if self._transport_policy == ice.TransportPolicy.ALL:
                candidates.append(protocol.local_candidate)

        self._protocols += host_protocols

        tasks: list[asyncio.Task[tuple[Any, Any | None]]] = []

        if self.stun_server:
            for protocol in host_protocols:
                if ipaddress.ip_address(protocol.local_candidate.host).version == 4:
                    tasks.append(
                        asyncio.create_task(
                            ice.server_reflexive_candidate(protocol, self.stun_server)
                        )
                    )

        if self.turn_server:
            tasks.append(
                asyncio.create_task(
                    ice.relayed_candidate(
                        component=component,
                        protocol_factory=lambda: ice.StunProtocol(self),
                        turn_server=self.turn_server,
                        turn_username=self.turn_username,
                        turn_password=self.turn_password,
                        turn_ssl=self.turn_ssl,
                        turn_transport=self.turn_transport,
                    )
                )
            )

        if tasks:
            done, pending = await asyncio.wait(tasks, timeout=timeout)
            for task in done:
                if task.exception() is None:
                    candidate, protocol = task.result()
                    candidates.append(candidate)
                    if protocol is not None:
                        self._protocols.append(protocol)
            for task in pending:
                task.cancel()

        return candidates

    ice.Connection.get_component_candidates = get_component_candidates_in_range
    ice._hairddae_udp_port_range = (min_port, max_port)
    logger.info("configured aioice udp port range patch: %s-%s", min_port, max_port)
