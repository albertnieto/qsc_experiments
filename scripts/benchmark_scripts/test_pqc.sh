#!/bin/bash
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
IMAGE="qsc-experiments:local"

echo "=== Building Docker Image with PQC ==="
docker build -t "$IMAGE" .

echo ""
echo "=== Running Phase 0 Demo ==="
docker run --rm "$IMAGE" python tests/demos/phase0_demo.py

echo ""
echo "=== Running Phase 1 Tests ==="
docker run --rm "$IMAGE" pytest tests/test_phase1_identity.py -v

echo ""
echo "=== Running Phase 2 Tests ==="
docker run --rm "$IMAGE" pytest tests/test_phase2_workflow.py -v

echo ""
echo "=== Running Phase 3 Tests ==="
docker run --rm "$IMAGE" pytest tests/test_phase3_resilience.py -v

echo ""
echo "=== All Tests Complete ==="
