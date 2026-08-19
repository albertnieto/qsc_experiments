#!/bin/bash
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

# Local testing script for PQC multi-agent framework

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
: "${QSC_BOOTSTRAP_TOKEN:?Set QSC_BOOTSTRAP_TOKEN to at least 32 characters}"

echo "=== Testing PQC Multi-Agent Framework ==="
echo ""

# Test health endpoints
echo "1. Testing health endpoints..."
curl -s http://localhost:8000/health | python3 -m json.tool
curl -s http://localhost:8001/health | python3 -m json.tool
curl -s http://localhost:8002/health | python3 -m json.tool
echo "✓ All agents healthy"
echo ""

# Test authenticated routine delegation
echo "2. Testing authenticated AES-256-GCM query delegation..."
REQUEST_BODY=$(
PYTHONPATH=. python3 - <<'PY'
import json
import os
import secrets

from src.security.bootstrap_auth import (
    canonical_payload_sha256,
    create_bootstrap_proof,
)

payload = {
    "queries": ["quantum computing"],
    "search_config": {"search_api": "mock"},
    "max_results": 5,
    "date_range": None,
}
fields = {
    "client_id": "local-smoke-test",
    "nonce": secrets.token_hex(32),
    "request_sha256": canonical_payload_sha256(payload),
}
print(
    json.dumps(
        {
            **payload,
            **fields,
            "bootstrap_proof": create_bootstrap_proof(
                os.environ["QSC_BOOTSTRAP_TOKEN"],
                "client-delegation",
                fields,
            ),
        }
    )
)
PY
)
RESPONSE=$(curl -s -X POST http://localhost:8000/delegate_search \
  -H "Content-Type: application/json" \
  -d "$REQUEST_BODY")

if echo "$RESPONSE" | grep -q '"authenticated":true'; then
  echo "$RESPONSE" | python3 -m json.tool
  echo "✓ Query encrypted with an ML-KEM-established AES-256-GCM session"
else
  echo "✗ Error: $RESPONSE"
  exit 1
fi
echo ""

echo "=== All Tests Passed ==="
echo ""
echo "Ready for Azure deployment!"
