# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Explicit QRNG providers for simulation and real-device collection.

The default provider is a labeled OS CSPRNG simulation. A real device can be
connected through a command that emits raw bytes (hex or base64), so hardware
measurements remain independently auditable rather than being silently
represented by classical randomness.
"""
from __future__ import annotations

import base64
import os
import subprocess
import time
import secrets
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class QRNGProvider:
    """Provider interface implemented by simulation and device adapters."""

    measurement_type = "simulated"

    def generate_bytes(self, length: int) -> bytes:
        raise NotImplementedError

    def metadata(self) -> Dict[str, Any]:
        return {"measurement_type": self.measurement_type}


class SimulatedQRNGProvider(QRNGProvider):
    """Use the operating-system CSPRNG while explicitly labeling it simulated."""

    def generate_bytes(self, length: int) -> bytes:
        return secrets.token_bytes(length)

    def metadata(self) -> Dict[str, Any]:
        return {
            "measurement_type": "simulated",
            "provider": "python.secrets",
            "quantum_source": False,
        }


class CommandQRNGProvider(QRNGProvider):
    """Read bytes from a collaborator-supplied hardware adapter command.

    The command must write exactly one hex or base64 encoded value to stdout.
    It is intentionally external to this repository because device SDKs differ.
    """

    measurement_type = "hardware"

    def __init__(
        self,
        command: str,
        *,
        encoding: str = "hex",
        device_name: str = "unspecified",
        sdk_version: str = "unspecified",
    ):
        if encoding not in {"hex", "base64"}:
            raise ValueError("encoding must be 'hex' or 'base64'")
        self.command = command
        self.encoding = encoding
        self.device_name = device_name
        self.sdk_version = sdk_version

    def generate_bytes(self, length: int) -> bytes:
        started = time.perf_counter()
        completed = subprocess.run(
            [self.command, str(length)],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        raw = completed.stdout.strip().encode("ascii")
        result = bytes.fromhex(raw.decode()) if self.encoding == "hex" else base64.b64decode(raw)
        if len(result) != length:
            raise ValueError(f"QRNG adapter returned {len(result)} bytes; expected {length}")
        self.last_latency_ms = (time.perf_counter() - started) * 1000
        return result

    def metadata(self) -> Dict[str, Any]:
        return {
            "measurement_type": "hardware",
            "provider": "external-command-adapter",
            "device_name": self.device_name,
            "sdk_version": self.sdk_version,
            "quantum_source": True,
            "adapter_command": self.command,
            "encoding": self.encoding,
        }


class QRNGSimulator:
    """Compatibility facade with explicit simulated or hardware providers."""

    def __init__(
        self,
        use_quantum: bool = False,
        *,
        provider: Optional[QRNGProvider] = None,
    ):
        self.provider = provider or (
            CommandQRNGProvider(
                os.environ["QSC_QRNG_COMMAND"],
                encoding=os.environ.get("QSC_QRNG_ENCODING", "hex"),
                device_name=os.environ.get("QSC_QRNG_DEVICE", "external-device"),
                sdk_version=os.environ.get("QSC_QRNG_SDK_VERSION", "unspecified"),
            )
            if use_quantum and os.environ.get("QSC_QRNG_COMMAND")
            else SimulatedQRNGProvider()
        )
        self.use_quantum = self.provider.measurement_type == "hardware"
        logger.info("QRNGSimulator: Initialized (%s)", self.provider.metadata())

    def generate_bytes(self, length: int = 32) -> bytes:
        return self.provider.generate_bytes(length)

    def metadata(self) -> Dict[str, Any]:
        return self.provider.metadata()

    def generate_query_id(self) -> str:
        """Generate a unique query ID using QRNG."""
        random_bytes = self.generate_bytes(16)
        query_id = random_bytes.hex()
        logger.debug(f"QRNGSimulator: Generated query_id: {query_id}")
        return query_id

    def generate_nonce(self, length: int = 32) -> str:
        """Generate a random nonce for challenge-response."""
        random_bytes = self.generate_bytes(length)
        return random_bytes.hex()

    def generate_session_key(self, key_size: int = 32) -> bytes:
        """Generate a symmetric encryption key."""
        return self.generate_bytes(key_size)
