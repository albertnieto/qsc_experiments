# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Reproducibility metadata for benchmark result files."""

from __future__ import annotations

import os
import platform
import hashlib
import ssl
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _git_revision() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except Exception:
        return "unavailable"


def _git_dirty_metadata() -> Dict[str, Any]:
    """Record whether the result came from an uncommitted worktree."""
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        return {
            "git_dirty": bool(status.strip()),
            "git_status_sha256": hashlib.sha256(status.encode()).hexdigest(),
        }
    except Exception:
        return {"git_dirty": None, "git_status_sha256": "unavailable"}


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unavailable"


def _sysctl(name: str) -> str:
    """Read a macOS hardware field without adding a dependency."""
    try:
        return subprocess.run(
            ["sysctl", "-n", name],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except Exception:
        return "unspecified"


def run_metadata(
    *,
    repetitions: Optional[int] = None,
    seed: Optional[int] = None,
    algorithms: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    physical_cores = os.environ.get(
        "QSC_PHYSICAL_CORES",
        _sysctl("hw.physicalcpu"),
    )
    if not physical_cores.isdigit():
        physical_cores = str(os.cpu_count() or "unspecified")
    ram_bytes = os.environ.get("QSC_RAM_BYTES", _sysctl("hw.memsize"))
    if not ram_bytes.isdigit():
        try:
            ram_bytes = str(
                os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
            )
        except (AttributeError, OSError, ValueError):
            ram_bytes = "unspecified"
    cpu = os.environ.get(
        "QSC_CPU_MODEL",
        _sysctl("machdep.cpu.brand_string"),
    )
    if not cpu or cpu == "unspecified":
        cpu = platform.processor() or platform.machine() or "unspecified"
    metadata = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_revision": _git_revision(),
        "python": sys.version.split()[0],
        "python_architecture": platform.machine(),
        "platform": platform.platform(),
        "cpu": cpu,
        "physical_cores": (
            int(physical_cores) if physical_cores.isdigit() else physical_cores
        ),
        "ram_bytes": int(ram_bytes) if ram_bytes.isdigit() else ram_bytes,
        "hostname": os.environ.get("QSC_HOST_LABEL", "redacted"),
        "library_versions": {
            "liboqs-python": _package_version("liboqs-python"),
            "cryptography": _package_version("cryptography"),
            "PyNaCl": _package_version("PyNaCl"),
            "openssl": ssl.OPENSSL_VERSION,
        },
        "warmup_policy": os.environ.get("QSC_WARMUP_POLICY", "none"),
        "summary_statistic": "arithmetic mean with min/max",
        "ci95_method": "1.96 * sample standard deviation / sqrt(n)",
        "azure_resource_group": os.environ.get("AZURE_RESOURCE_GROUP", "not-applicable"),
        "repetitions": repetitions,
        "seed": seed,
        "algorithms": algorithms
        or {
            "kem": "ML-KEM-768",
            "signature": "ML-DSA-65",
            "classical_signature": "Ed25519",
            "symmetric": "AES-256-GCM",
            "classical_kex": "ECDH-P256",
        },
    }
    metadata.update(_git_dirty_metadata())
    return metadata


def annotate(
    payload: Dict[str, Any],
    *,
    measurement_type: str,
    provenance: str,
    repetitions: Optional[int] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    if measurement_type not in {
        "measured",
        "modeled",
        "simulated",
        "mixed",
        "M-local",
        "M-cloud",
        "M-QRNG",
        "Model-QKD",
        "S-simulation",
    }:
        raise ValueError(
            "measurement_type must be a canonical M-/Model-/S- class or legacy class"
        )
    payload["measurement_type"] = measurement_type
    payload["provenance"] = provenance
    payload["run_metadata"] = run_metadata(repetitions=repetitions, seed=seed)
    return payload
