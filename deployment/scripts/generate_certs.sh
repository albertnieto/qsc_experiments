#!/bin/bash
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

# Generate a private development CA and hostname-verified TLS certificates.

set -euo pipefail

QSC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CERTS_DIR="${QSC_CERTS_DIR:-$QSC_ROOT/certs}"
ORCHESTRATOR_DNS_NAMES="${ORCHESTRATOR_DNS_NAMES:-orchestrator-proxy,orchestrator,localhost}"
WORKER_DNS_NAMES="${WORKER_DNS_NAMES:-worker1-proxy,worker2-proxy,worker,localhost}"
mkdir -p "$CERTS_DIR"

temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT

write_extensions() {
    local output="$1"
    local dns_names="$2"
    local sans=""
    local name
    IFS=',' read -ra names <<< "$dns_names"
    for name in "${names[@]}"; do
        name="${name#"${name%%[![:space:]]*}"}"
        name="${name%"${name##*[![:space:]]}"}"
        [ -n "$name" ] || continue
        if [ -n "$sans" ]; then
            sans+=","
        fi
        sans+="DNS:$name"
    done
    if [[ ",$dns_names," == *",localhost,"* ]]; then
        sans+=",IP:127.0.0.1"
    fi
    cat > "$output" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=$sans
EOF
}

issue_certificate() {
    local name="$1"
    local common_name="$2"
    local dns_names="$3"
    local extensions="$temp_dir/$name.ext"
    write_extensions "$extensions" "$dns_names"
    openssl req -newkey rsa:3072 -nodes \
        -keyout "$CERTS_DIR/$name.key" \
        -out "$temp_dir/$name.csr" \
        -subj "/O=QSC Development/OU=Deep Research/CN=$common_name"
    openssl x509 -req \
        -in "$temp_dir/$name.csr" \
        -CA "$CERTS_DIR/ca.crt" \
        -CAkey "$CERTS_DIR/ca.key" \
        -CAcreateserial \
        -out "$CERTS_DIR/$name.crt" \
        -days 365 \
        -sha256 \
        -extfile "$extensions"
}

echo "Generating a development CA and verified TLS certificates..."
openssl req -x509 -newkey rsa:3072 -nodes \
    -keyout "$CERTS_DIR/ca.key" \
    -out "$CERTS_DIR/ca.crt" \
    -days 365 \
    -sha256 \
    -subj "/O=QSC Development/OU=Deep Research/CN=QSC Development CA"

issue_certificate "orchestrator" "orchestrator" "$ORCHESTRATOR_DNS_NAMES"
issue_certificate "worker" "worker" "$WORKER_DNS_NAMES"

rm -f "$CERTS_DIR/ca.srl"
chmod 600 "$CERTS_DIR"/*.key
chmod 644 "$CERTS_DIR"/*.crt

echo "Certificates generated in $CERTS_DIR/"
echo "Trust $CERTS_DIR/ca.crt through QSC_CA_BUNDLE."
echo "For production, replace this private CA with managed certificates."
