#!/bin/bash
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "=== Building Docker Image ==="
docker build -t qsc-experiments:local .

echo ""
echo "=== Running KEM Benchmark (Kyber vs ECDH) ==="
docker run --rm -v "$ROOT/results:/app/results" qsc-experiments:local python tests/benchmarks/benchmark_kem.py

echo ""
echo "=== Results saved to ./results/kem_benchmark_results.json ==="
cat results/kem_benchmark_results.json
