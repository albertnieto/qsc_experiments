#!/bin/bash
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
IMAGE="qsc-experiments:local"

echo "=== Building Docker Image ==="
docker build -t "$IMAGE" .

echo ""
echo "=== Running Benchmarks ==="
docker run --rm -v "$ROOT/results:/app/results" "$IMAGE" python tests/benchmarks/benchmark_pqc.py

echo ""
echo "=== Running Comparative Benchmarks ==="
docker run --rm -v "$ROOT/results:/app/results" "$IMAGE" python tests/benchmarks/benchmark_comparative.py

echo ""
echo "=== Running Scalability Benchmarks ==="
docker run --rm -v "$ROOT/results:/app/results" "$IMAGE" python tests/benchmarks/benchmark_scalability.py

echo ""
echo "=== Running Security Resilience Benchmark ==="
docker run --rm -e QSC_SECURITY_TRANSACTIONS="${QSC_SECURITY_TRANSACTIONS:-100000}" -v "$ROOT/results:/app/results" "$IMAGE" python tests/benchmarks/benchmark_security.py

echo ""
echo "=== Generating Plots ==="
docker run --rm -v "$ROOT/results:/app/results" "$IMAGE" python tests/benchmarks/generate_plots.py

echo ""
echo "=== Generating Paper Results ==="
docker run --rm -v "$ROOT/results:/app/results" "$IMAGE" python tests/benchmarks/generate_paper_results.py

echo ""
echo "=== Results saved to ./results/ ==="
ls -lh results/
