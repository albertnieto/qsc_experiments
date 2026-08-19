#!/bin/bash
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "=== Building Docker Image ==="
docker build -t qsc-experiments:local .

echo ""
echo "=== Running Unified Framework Lifecycle Benchmark ==="
docker run --rm -e QSC_SECURITY_TRANSACTIONS="${QSC_SECURITY_TRANSACTIONS:-100000}" -v "$ROOT/results:/app/results" qsc-experiments:local python tests/benchmarks/benchmark_framework_lifecycle.py

echo ""
echo "=== Results saved to ./results/ ==="
ls -lh results/lifecycle_benchmark_results.json
