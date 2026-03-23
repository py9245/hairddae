from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RtcTransportStats:
    first_remote_excluded: bool = False
    sample_count: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    last_ms: float = 0.0

    def record(self, sample_ms: float) -> bool:
        normalized_ms = max(0.0, float(sample_ms))
        self.last_ms = normalized_ms
        if not self.first_remote_excluded:
            self.first_remote_excluded = True
            return False

        self.sample_count += 1
        self.total_ms += normalized_ms
        if normalized_ms > self.max_ms:
            self.max_ms = normalized_ms
        return True

    @property
    def average_ms(self) -> float:
        if self.sample_count <= 0:
            return 0.0
        return self.total_ms / self.sample_count
