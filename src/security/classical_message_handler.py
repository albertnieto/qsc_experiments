# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Classical message handler using Ed25519.
"""
import json
import hashlib
from typing import Dict, Any
from src.security.classical_identity import ClassicalIdentity


class ClassicalMessageHandler:
    """Handle message signing/verification with Ed25519."""

    def __init__(self, identity: ClassicalIdentity):
        self.identity = identity

    def sign_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sign a message payload."""
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        signature = self.identity.sign(payload_bytes)
        
        return {
            "payload": payload,
            "signature": signature.hex(),
            "public_key": self.identity.get_public_key().hex()
        }

    def verify_message(self, signed_message: Dict[str, Any], public_key: bytes) -> bool:
        """Verify a signed message."""
        try:
            payload = signed_message["payload"]
            signature = bytes.fromhex(signed_message["signature"])
            payload_bytes = json.dumps(payload, sort_keys=True).encode()
            return self.identity.verify(payload_bytes, signature, public_key)
        except Exception:
            return False
