#!/usr/bin/env python3
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Measure Azure PQC-TLS reachability latency and report QKD separately.

The current sidecar deployment exposes health endpoints, so this harness
measures the deployed transport path without pretending that health checks are
full application transactions. Set the three endpoint variables before use.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.security.qkd_simulator import QKDSimulator  # noqa: E402
from src.security.benchmark_metadata import run_metadata  # noqa: E402

TLS_VERIFY = os.environ.get("QSC_CA_BUNDLE") or True


def measure(role: str, url: str, repetitions: int) -> dict:
    if "." in role or ":" in role:
        raise ValueError("url_role must be a role label, not a host")
    samples = []
    statuses = []
    for _ in range(repetitions):
        started = time.perf_counter()
        response = requests.get(url, verify=TLS_VERIFY, timeout=30)
        samples.append((time.perf_counter() - started) * 1000)
        statuses.append(response.status_code)
    return {
        "url_role": role,
        "repetitions": repetitions,
        "status_codes": statuses,
        "mean_ms": statistics.mean(samples),
        "median_ms": statistics.median(samples),
        "min_ms": min(samples),
        "max_ms": max(samples),
        "measurement_type": "M-cloud",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qkd-latency-ms", type=float, default=10.0)
    args = parser.parse_args()
    endpoints = {
        "orchestrator": os.environ.get("QSC_ORCHESTRATOR_URL"),
        "worker1": os.environ.get("QSC_WORKER1_URL"),
        "worker2": os.environ.get("QSC_WORKER2_URL"),
    }
    missing = [name for name, url in endpoints.items() if not url]
    if missing:
        raise SystemExit(f"Set endpoint variables for: {', '.join(missing)}")

    endpoint_results = {
        name: measure(name, url, args.repetitions)
        for name, url in endpoints.items()
    }
    qkd = QKDSimulator(establishment_latency_ms=args.qkd_latency_ms)
    output = {
        "measurement_type": "M-cloud",
        "provenance": (
            "M-cloud PQC-TLS health-endpoint RTT; this is transport reachability, "
            "not a complete seven-channel application transaction"
        ),
        "tls_certificate_verification": True,
        "tls_trust_source": (
            "QSC_CA_BUNDLE" if os.environ.get("QSC_CA_BUNDLE") else "system"
        ),
        "run_metadata": run_metadata(repetitions=args.repetitions),
        "endpoints": endpoint_results,
        "seven_channel_mapping": {
            "1": "orchestrator",
            "2": "orchestrator-worker handshake path; health proxy only",
            "3": "orchestrator",
            "4": "worker1",
            "5": "worker1",
            "6": "worker2",
            "7": "orchestrator",
        },
        "qkd_model": {
            "measurement_type": qkd.measurement_type,
            "parameters": qkd.metadata(),
            "note": "Not included in measured Azure RTT values.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
