#!/usr/bin/env bash
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

# Run all locally reproducible Phase I benchmarks from qsc_experiments.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

echo "=== QSC Experiments — benchmark suite ==="
echo "Output directory: $ROOT/results"

PYTHON="${PYTHON:-python3}"

if [ -z "${QSC_AUDIT_LOG:-}" ]; then
    BENCHMARK_AUDIT_FILE="$(mktemp /tmp/qsc-benchmark-audit.XXXXXX)"
    export QSC_AUDIT_LOG="$BENCHMARK_AUDIT_FILE"
    export QSC_AUDIT_MAX_BYTES="${QSC_AUDIT_MAX_BYTES:-209715200}"
    trap 'rm -f "$BENCHMARK_AUDIT_FILE"' EXIT
    echo "Audit events: fresh bounded temporary JSONL file"
fi

"$PYTHON" tests/benchmarks/benchmark_framework_lifecycle.py
"$PYTHON" tests/benchmarks/benchmark_comparative.py
"$PYTHON" tests/benchmarks/benchmark_pqc.py
"$PYTHON" tests/benchmarks/benchmark_kem.py
"$PYTHON" tests/benchmarks/benchmark_scalability.py
"$PYTHON" tests/benchmarks/benchmark_security.py
"$PYTHON" tests/benchmarks/benchmark_full_framework.py
"$PYTHON" tests/benchmarks/generate_paper_results.py
"$PYTHON" tests/benchmarks/generate_plots.py
"$PYTHON" scripts/benchmark_scripts/plots.py

echo "=== Local outputs complete. Check results/. ==="
echo "M-cloud and M-QRNG artifacts require their documented external acquisition workflows."
