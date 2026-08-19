# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Classical cryptographic identity using Ed25519.
"""
from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import RawEncoder


class ClassicalIdentity:
    """Classical Ed25519-based identity for comparison."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.signing_key = SigningKey.generate()
        self.verify_key = self.signing_key.verify_key

    def get_public_key(self) -> bytes:
        """Return public key."""
        return bytes(self.verify_key)

    def sign(self, message: bytes) -> bytes:
        """Sign a message."""
        return self.signing_key.sign(message).signature

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify a signature."""
        try:
            verify_key = VerifyKey(public_key, encoder=RawEncoder)
            verify_key.verify(message, signature)
            return True
        except Exception:
            return False
