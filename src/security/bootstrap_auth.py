# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Out-of-band bootstrap authentication for HTTP agent identities."""

from __future__ import annotations

import hashlib
import hmac
import json
import struct
from typing import Any, Mapping


DOMAIN = b"QSC-HTTP-BOOTSTRAP/v1"


def _field(label: bytes, value: bytes) -> bytes:
    return (
        struct.pack(">H", len(label))
        + label
        + struct.pack(">I", len(value))
        + value
    )


def require_bootstrap_secret(secret: str) -> bytes:
    """Validate and encode the deployment bootstrap secret."""
    if len(secret) < 32:
        raise RuntimeError(
            "QSC_BOOTSTRAP_TOKEN must contain at least 32 characters"
        )
    return secret.encode("utf-8")


def canonical_payload_sha256(payload: Any) -> str:
    """Hash a JSON-compatible request using a stable serialization."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def bootstrap_message(
    purpose: str,
    fields: Mapping[str, str],
) -> bytes:
    """Create a canonical, purpose-bound bootstrap transcript."""
    encoded = [
        _field(b"domain", DOMAIN),
        _field(b"purpose", purpose.encode("ascii")),
    ]
    for label, value in sorted(fields.items()):
        encoded.append(
            _field(label.encode("utf-8"), value.encode("utf-8"))
        )
    return b"".join(encoded)


def create_bootstrap_proof(
    secret: str,
    purpose: str,
    fields: Mapping[str, str],
) -> str:
    """Return an HMAC-SHA-256 proof without transmitting the secret."""
    return hmac.new(
        require_bootstrap_secret(secret),
        bootstrap_message(purpose, fields),
        hashlib.sha256,
    ).hexdigest()


def verify_bootstrap_proof(
    secret: str,
    purpose: str,
    fields: Mapping[str, str],
    proof: str,
) -> bool:
    """Verify a deployment bootstrap proof in constant time."""
    expected = create_bootstrap_proof(secret, purpose, fields)
    return hmac.compare_digest(expected, proof)
