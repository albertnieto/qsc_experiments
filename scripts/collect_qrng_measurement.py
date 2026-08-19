#!/usr/bin/env python3
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Collect auditable QRNG-provider measurements.

For a real device, set ``QSC_QRNG_COMMAND`` to a small local adapter that
accepts a byte count and prints hex or base64 bytes. The adapter is deliberately
owned by the device operator because vendor SDKs are not uniform.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.security.qrng_simulator import (  # noqa: E402
    CommandQRNGProvider,
    QRNGSimulator,
    SimulatedQRNGProvider,
)
from src.security.benchmark_metadata import run_metadata  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--bytes", type=int, default=32, dest="sample_bytes")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("hardware", "simulated"), default="simulated")
    parser.add_argument("--command", help="hardware adapter executable")
    parser.add_argument("--encoding", choices=("hex", "base64"), default="hex")
    parser.add_argument("--device-name", default="unspecified")
    parser.add_argument("--sdk-version", default="unspecified")
    args = parser.parse_args()
    if args.samples < 1 or args.sample_bytes < 1:
        raise SystemExit("--samples and --bytes must be positive")
    if args.mode == "hardware" and not args.command:
        raise SystemExit("--command is required in hardware mode")

    provider = (
        CommandQRNGProvider(
            args.command,
            encoding=args.encoding,
            device_name=args.device_name,
            sdk_version=args.sdk_version,
        )
        if args.mode == "hardware"
        else SimulatedQRNGProvider()
    )
    qrng = QRNGSimulator(provider=provider)
    latencies = []
    digests = []
    for _ in range(args.samples):
        started = time.perf_counter()
        value = qrng.generate_bytes(args.sample_bytes)
        latencies.append((time.perf_counter() - started) * 1000)
        digests.append(hashlib.sha256(value).hexdigest())

    output = {
        "measurement_type": "M-QRNG" if args.mode == "hardware" else "S-simulation",
        "provenance": (
            "M-QRNG: collaborator/device adapter measurement"
            if args.mode == "hardware"
            else "S-simulation: python.secrets provider"
        ),
        "run_metadata": {
            **run_metadata(repetitions=args.samples),
            "samples": args.samples,
            "sample_bytes": args.sample_bytes,
        },
        "provider": provider.metadata(),
        "metrics": {
            "mean_latency_ms": statistics.mean(latencies),
            "median_latency_ms": statistics.median(latencies),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "throughput_bytes_per_second": (
                args.samples * args.sample_bytes / (sum(latencies) / 1000)
            ),
        },
        "sample_sha256": digests,
        "disclaimer": (
            "Hardware measurements are valid only when measurement_type=hardware "
            "and the adapter metadata identifies the real device."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
