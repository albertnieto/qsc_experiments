# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Context-bound hybrid session keys and AES-256-GCM protection.

The combiner keeps the underlying inputs distinct instead of concatenating
unlabelled byte strings.  It is intentionally explicit about the protocol
mode and transcript so a peer cannot silently remove QKD or substitute a
different session context.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import struct
from dataclasses import dataclass
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


DOMAIN = b"QSC-HYBRID-SESSION-KEY/v1"
SESSION_AUTH_DOMAIN = b"QSC-SESSION-AUTH/v1"
AES256_KEY_SIZE = 32


def _field(label: bytes, value: bytes) -> bytes:
    """Encode a labeled field with an unambiguous length prefix."""
    return (
        struct.pack(">H", len(label))
        + label
        + struct.pack(">I", len(value))
        + value
    )


def _transcript(
    *,
    sender_id: str,
    receiver_id: str,
    mode: str,
    pqc_ciphertext: bytes,
    session_context: bytes,
    qkd_epoch: Optional[str],
) -> bytes:
    return b"".join(
        (
            _field(b"domain", DOMAIN),
            _field(b"sender", sender_id.encode("utf-8")),
            _field(b"receiver", receiver_id.encode("utf-8")),
            _field(b"mode", mode.encode("ascii")),
            _field(b"kem-ct", pqc_ciphertext),
            _field(b"context", session_context),
            _field(b"qkd-epoch", (qkd_epoch or "").encode("utf-8")),
        )
    )


def session_auth_message(
    *,
    sender_id: str,
    receiver_id: str,
    session_context: bytes,
    ciphertext: bytes,
    qrng_entropy: bytes,
    qkd_epoch: Optional[str] = None,
) -> bytes:
    """Return the canonical ML-DSA-authenticated session request.

    The receiver verifies this value against a previously trusted sender key
    before decapsulating the ML-KEM ciphertext.
    """
    return b"".join(
        (
            _field(b"domain", SESSION_AUTH_DOMAIN),
            _field(b"sender", sender_id.encode("utf-8")),
            _field(b"receiver", receiver_id.encode("utf-8")),
            _field(b"context", session_context),
            _field(b"kem-ct", ciphertext),
            _field(b"qrng-entropy", qrng_entropy),
            _field(b"qkd-epoch", (qkd_epoch or "").encode("utf-8")),
        )
    )


@dataclass(frozen=True)
class SessionKey:
    """Derived session key plus auditable derivation metadata."""

    key: bytes
    mode: str
    transcript_hash: str


def derive_session_key(
    *,
    pqc_secret: bytes,
    pqc_ciphertext: bytes,
    sender_id: str,
    receiver_id: str,
    session_context: bytes,
    qrng_entropy: bytes = b"",
    qkd_secret: Optional[bytes] = None,
    qkd_epoch: Optional[str] = None,
) -> SessionKey:
    """Derive a 256-bit key from domain-separated hybrid inputs.

    PQC is mandatory. QKD is an optional second independent secret. QRNG
    entropy is treated as a labeled protocol input, not as a cryptographic
    primitive or a replacement for KEM authentication.
    """
    if not pqc_secret:
        raise ValueError("pqc_secret must not be empty")
    if not pqc_ciphertext:
        raise ValueError("pqc_ciphertext must not be empty")
    if not sender_id or not receiver_id:
        raise ValueError("both endpoint identities are required")
    if sender_id == receiver_id:
        raise ValueError("endpoint identities must differ")
    if not session_context:
        raise ValueError("session_context must not be empty")
    if qkd_secret is not None and not qkd_epoch:
        raise ValueError("qkd_epoch is required when qkd_secret is supplied")

    mode = "pqc+qkd+qrng" if qkd_secret is not None else "pqc+qrng"
    transcript = _transcript(
        sender_id=sender_id,
        receiver_id=receiver_id,
        mode=mode,
        pqc_ciphertext=pqc_ciphertext,
        session_context=session_context,
        qkd_epoch=qkd_epoch,
    )
    transcript_hash = hashlib.sha256(transcript).hexdigest()

    # HKDF-Extract with a transcript-derived salt and labeled, length-prefixed
    # input components. This prevents ambiguity and binds mode/context.
    salt = hmac.new(DOMAIN, transcript, hashlib.sha256).digest()
    ikm = b"".join(
        (
            _field(b"pqc-secret", pqc_secret),
            _field(b"qkd-secret", qkd_secret or b""),
            _field(b"qrng-entropy", qrng_entropy),
        )
    )
    pseudorandom_key = hmac.new(salt, ikm, hashlib.sha256).digest()
    info = b"".join(
        (
            _field(b"expand-domain", DOMAIN),
            _field(b"transcript-hash", bytes.fromhex(transcript_hash)),
            _field(b"purpose", b"AES-256-GCM session key"),
        )
    )
    output = hmac.new(
        pseudorandom_key,
        info + b"\x01",
        hashlib.sha256,
    ).digest()
    return SessionKey(output[:AES256_KEY_SIZE], mode, transcript_hash)


def encrypt_aes256_gcm(
    key: bytes,
    plaintext: bytes,
    *,
    aad: bytes = b"",
    nonce: Optional[bytes] = None,
) -> tuple[bytes, bytes]:
    """Encrypt with AES-256-GCM and return ``(nonce, ciphertext)``."""
    if len(key) != AES256_KEY_SIZE:
        raise ValueError("AES-256-GCM requires a 32-byte key")
    actual_nonce = nonce or secrets.token_bytes(12)
    if len(actual_nonce) != 12:
        raise ValueError("AES-GCM nonce must be 12 bytes")
    return actual_nonce, AESGCM(key).encrypt(actual_nonce, plaintext, aad)


def decrypt_aes256_gcm(
    key: bytes,
    nonce: bytes,
    ciphertext: bytes,
    *,
    aad: bytes = b"",
) -> bytes:
    """Decrypt and authenticate an AES-256-GCM message."""
    if len(key) != AES256_KEY_SIZE:
        raise ValueError("AES-256-GCM requires a 32-byte key")
    if len(nonce) != 12:
        raise ValueError("AES-GCM nonce must be 12 bytes")
    return AESGCM(key).decrypt(nonce, ciphertext, aad)
