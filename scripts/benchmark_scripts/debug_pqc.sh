#!/bin/bash
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.


echo "=== Building Docker Image ==="
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
docker build -t qsc-experiments:local .

echo ""
echo "=== Starting Interactive Debug Session ==="
echo "You can now run:"
echo "  python tests/demos/phase0_demo.py"
echo "  pytest tests/test_phase1_identity.py -v"
echo "  python -c 'import oqs; print(oqs.get_enabled_sig_mechanisms())'"
echo ""

docker run --rm -it qsc-experiments:local /bin/bash
