# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Post-quantum identity management using ML-DSA and ML-KEM."""
import logging
import oqs

logger = logging.getLogger(__name__)


class PQCIdentity:
    """Manages PQC key pairs and signing operations for agent identity."""

    def __init__(
        self,
        agent_id: str,
        algorithm: str = "ML-DSA-65",
        kem_algorithm: str = "ML-KEM-768",
    ):
        self.agent_id = agent_id
        self.algorithm = algorithm
        self.signer = oqs.Signature(algorithm)
        self.public_key_bytes = self.signer.generate_keypair()
        self.kem_algorithm = kem_algorithm
        try:
            self.kem = oqs.KeyEncapsulation(kem_algorithm)
        except Exception:
            # Older liboqs releases used the pre-standard name.
            self.kem_algorithm = "Kyber768"
            self.kem = oqs.KeyEncapsulation(self.kem_algorithm)
        self.kem_public_key_bytes = self.kem.generate_keypair()
        logger.info(f"PQCIdentity: Generated {algorithm} key pair for {agent_id}")

    def get_public_key(self) -> bytes:
        """Return public key in raw bytes format."""
        return self.public_key_bytes

    def sign(self, message: bytes) -> bytes:
        """Sign a message with private key."""
        return self.signer.sign(message)

    def verify(self, message: bytes, signature: bytes, public_key_bytes: bytes) -> bool:
        """Verify a signature using a public key."""
        try:
            verifier = oqs.Signature(self.algorithm)
            return verifier.verify(message, signature, public_key_bytes)
        except Exception as e:
            logger.error(f"PQCIdentity: Signature verification failed: {e}")
            return False

    def get_kem_public_key(self) -> bytes:
        """Return the receiver's ML-KEM public key."""
        return self.kem_public_key_bytes

    def encapsulate(self, receiver_public_key: bytes) -> tuple[bytes, bytes]:
        """Encapsulate to a receiver; returns ``(ciphertext, sender_secret)``."""
        return self.kem.encap_secret(receiver_public_key)

    def decapsulate(self, ciphertext: bytes) -> bytes:
        """Decapsulate with this identity's private KEM state."""
        return self.kem.decap_secret(ciphertext)
