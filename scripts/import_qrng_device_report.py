#!/usr/bin/env python3
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Convert a collaborator's live QRNG probe into a QSC evidence artifact.

The Quantis handoff records live device throughput in a probe JSON and stores
the large capture separately.  This importer keeps the public QSC artifact
small while preserving the source hashes, device metadata, entropy diagnostics,
and the distinction between vendor-postprocessed output and detector-level raw
entropy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import a live QRNG probe into the QSC M-QRNG schema."
    )
    parser.add_argument("--probe-report", type=Path, required=True)
    parser.add_argument("--capture-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--measurement-date", required=True)
    parser.add_argument("--source-repository", default="external QRNG assessment")
    parser.add_argument("--source-commit", default="not recorded")
    parser.add_argument("--source-git-dirty", action="store_true")
    parser.add_argument("--operator", default="not recorded")
    parser.add_argument("--serial", default="not recorded")
    args = parser.parse_args()

    probe = load_json(args.probe_report)
    manifest = load_json(args.capture_manifest)
    source = probe.get("source", {})
    throughput = probe.get("throughput", {})
    raw = probe.get("raw", {})
    conditioned = probe.get("conditioned", {})

    if source.get("kind") != "live":
        raise SystemExit("probe report must describe a live capture")
    required_throughput = ("seconds_for_sample",)
    missing = [key for key in required_throughput if key not in throughput]
    if missing:
        raise SystemExit(f"probe report is missing throughput fields: {missing}")
    if not manifest.get("sha256") or not manifest.get("size_bytes"):
        raise SystemExit("capture manifest must include sha256 and size_bytes")

    host = manifest.get("host", {})
    capture_bytes = raw.get("n_bytes")
    capture_seconds = throughput["seconds_for_sample"]
    if not capture_bytes or capture_seconds <= 0:
        raise SystemExit("probe report must include positive byte/time values")
    bytes_per_second = capture_bytes / capture_seconds
    key_budget_bytes = throughput.get("raw_bytes_per_key", 1024)
    provider = {
        "measurement_type": "hardware",
        "provider": "ID Quantique Quantis USB",
        "device_name": manifest.get("model", probe.get("model", "unspecified")),
        "device_index": manifest.get("device_index", 0),
        "serial": args.serial,
        "firmware": manifest.get("firmware", probe.get("firmware", "unspecified")),
        "sdk_version": manifest.get(
            "cli_version", source.get("cli_version", "unspecified")
        ),
        "quantum_source": True,
        "output_mode": "vendor-postprocessed",
        "raw_detector_output_available": False,
    }

    artifact = {
        "measurement_type": "M-QRNG",
        "provenance": (
            "M-QRNG: live ID Quantique Quantis USB probe; "
            "vendor-postprocessed output"
        ),
        "run_metadata": {
            "timestamp_utc": args.measurement_date,
            "source_repository": args.source_repository,
            "source_git_revision": args.source_commit,
            "source_git_dirty": args.source_git_dirty,
            "python": host.get("python", "not recorded"),
            "platform": host.get("platform", "not recorded"),
            "hostname": host.get("node", "not recorded"),
            "operator": args.operator,
            "repetitions": 1,
            "samples": 1,
            "sample_bytes": raw.get("n_bytes"),
        },
        "provider": provider,
        "metrics": {
            "live_capture_bytes": capture_bytes,
            "live_capture_seconds": capture_seconds,
            "live_read_bytes_per_second": bytes_per_second,
            "live_read_mib_per_second": bytes_per_second / (1024 ** 2),
            "live_read_mbit_per_second": bytes_per_second * 8 / 1_000_000,
            "live_read_mibits_per_second": bytes_per_second * 8 / (1024 ** 2),
            "source_reported_mb_per_second": throughput.get(
                "measured_read_mb_s"
            ),
            "source_reported_mbit_per_second": throughput.get(
                "measured_read_mbit_s"
            ),
            "spec_mbit_per_second": throughput.get("spec_mbit_s", 4.0),
            "raw_bytes_per_256bit_key": key_budget_bytes,
            "device_limited_keys_per_second": (
                bytes_per_second / key_budget_bytes
            ),
        },
        "entropy_diagnostics": {
            "as_captured": raw,
            "after_von_neumann": conditioned,
            "conditioning": probe.get("conditioning", {}),
        },
        "artifacts": {
            "probe_report": {
                "sha256": sha256_file(args.probe_report),
                "size_bytes": args.probe_report.stat().st_size,
            },
            "capture_manifest": {
                "sha256": sha256_file(args.capture_manifest),
                "size_bytes": args.capture_manifest.stat().st_size,
            },
            "capture": {
                "sha256": manifest["sha256"],
                "size_bytes": manifest["size_bytes"],
            },
        },
        "limitations": [
            "EasyQuantis USB exposes vendor-postprocessed output, not detector-level raw entropy.",
            "The live throughput observation is device I/O; it is not the disk speed of a replayed capture.",
            "Decimal Mbit/s and binary MiB/s/Mibit/s are recomputed from captured bytes and elapsed seconds; source-reported labels are retained separately.",
            "The restart dataset restarted the host CLI process, not the physical USB entropy source.",
        ],
        "disclaimer": (
            "This artifact records a real-device provider observation and its "
            "provenance. It does not certify the inaccessible detector-level "
            "entropy source or establish cryptographic security by itself."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
