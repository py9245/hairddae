#!/usr/bin/env bash
set -euo pipefail

CERT_BASE="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$CERT_BASE/nginx/certs"
CERT_DIR="$CERT_BASE/nginx/certs"

openssl req -x509 -nodes -days 365 \
  -provider default \
  -newkey rsa:2048 \
  -keyout "$CERT_DIR/selfsigned.key" \
  -out "$CERT_DIR/selfsigned.crt" \
  -subj "/C=US/ST=NA/L=NA/O=Dev/OU=Dev/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

echo "Generated:"
ls -l "$CERT_DIR"/selfsigned.*
