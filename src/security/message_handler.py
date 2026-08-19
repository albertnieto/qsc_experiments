# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Authenticated message envelopes for secure agent communication."""
import json
import logging
from typing import Dict, Any
from cryptography.exceptions import InvalidTag
from src.security.hybrid_session_key import (
    SessionKey,
    decrypt_aes256_gcm,
    encrypt_aes256_gcm,
)

logger = logging.getLogger(__name__)


class MessageHandler:
    """Handles AEAD routine messages and ML-DSA artifact signatures."""

    def __init__(self, identity):
        self.identity = identity

    def sign_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sign a message payload."""
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        signature = self.identity.sign(payload_bytes)
        
        return {
            "payload": payload,
            "signature": signature.hex(),
            "agent_id": self.identity.agent_id,
            "public_key": self.identity.get_public_key().hex()
        }

    def verify_message(self, signed_message: Dict[str, Any], expected_public_key: bytes) -> bool:
        """Verify a signed message."""
        try:
            payload = signed_message["payload"]
            signature = bytes.fromhex(signed_message["signature"])
            public_key = bytes.fromhex(signed_message["public_key"])
            
            # Verify public key matches expected
            if public_key != expected_public_key:
                logger.error("MessageHandler: Public key mismatch")
                return False
            
            payload_bytes = json.dumps(payload, sort_keys=True).encode()
            return self.identity.verify(payload_bytes, signature, public_key)
            
        except Exception as e:
            logger.error(f"MessageHandler: Verification error: {e}")
            return False

    def encrypt_payload(
        self,
        payload: Dict[str, Any],
        session_key: SessionKey,
        *,
        aad: bytes,
    ) -> Dict[str, Any]:
        """Encrypt a routine payload with the authenticated session key.

        Session establishment authenticates the peers. AES-GCM then supplies
        confidentiality and integrity for routine traffic; ML-DSA signatures
        remain available through ``sign_message`` for independent artifacts.
        """
        plaintext = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        nonce, ciphertext = encrypt_aes256_gcm(
            session_key.key, plaintext, aad=aad
        )
        return {
            "mode": "aead",
            "session_id": session_key.transcript_hash,
            "nonce": nonce.hex(),
            "ciphertext": ciphertext.hex(),
            "aad": aad.hex(),
        }

    def decrypt_payload(
        self,
        envelope: Dict[str, Any],
        session_key: SessionKey,
        *,
        aad: bytes,
    ) -> Dict[str, Any]:
        """Decrypt and authenticate a routine payload envelope."""
        if envelope.get("mode") != "aead":
            raise ValueError("expected an AEAD message envelope")
        if envelope.get("session_id") != session_key.transcript_hash:
            raise ValueError("session identifier mismatch")
        encoded_aad = envelope.get("aad")
        if encoded_aad != aad.hex():
            raise ValueError("authenticated metadata mismatch")
        try:
            plaintext = decrypt_aes256_gcm(
                session_key.key,
                bytes.fromhex(envelope["nonce"]),
                bytes.fromhex(envelope["ciphertext"]),
                aad=aad,
            )
        except InvalidTag as exc:
            raise ValueError("AEAD authentication failed") from exc
        payload = json.loads(plaintext.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("authenticated payload must be a JSON object")
        return payload
