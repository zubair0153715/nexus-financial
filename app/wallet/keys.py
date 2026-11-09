"""Testnet-only key management (Stage 1 prototype).

TESTNET-ONLY derivation: addresses are derived as ``tnx1`` + the first 40
hex chars of ``sha256(uncompressed_public_key_bytes)``. This format exists
only for the prototype's simulated test network. It is NOT compatible with
any live network and must never be used with real funds.
"""

import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec


def generate_keypair() -> dict:
    """Generate a fresh SECP256K1 keypair.

    Returns {"private_key_hex", "public_key_hex", "address"}. The private
    key is returned to the caller only; it is never persisted by this module.
    """
    private_key = ec.generate_private_key(ec.SECP256K1())
    private_bytes = private_key.private_numbers().private_value.to_bytes(32, "big")
    public_numbers = private_key.public_key().public_numbers()
    public_bytes = public_numbers.x.to_bytes(32, "big") + public_numbers.y.to_bytes(32, "big")
    return {
        "private_key_hex": private_bytes.hex(),
        "public_key_hex": public_bytes.hex(),
        "address": address_from_public_key(public_bytes.hex()),
    }


def address_from_public_key(public_key_hex: str) -> str:
    """Derive the testnet address (``tnx1...``) from an uncompressed public key.

    TESTNET-ONLY: sha256 derivation, not compatible with any live network.
    """
    public_bytes = bytes.fromhex(public_key_hex)
    return "tnx1" + hashlib.sha256(public_bytes).hexdigest()[:40]


def sign_message(private_key_hex: str, message: str) -> str:
    """Sign a message with a private key; returns DER signature hex."""
    private_value = int.from_bytes(bytes.fromhex(private_key_hex), "big")
    private_key = ec.derive_private_key(private_value, ec.SECP256K1())
    signature = private_key.sign(message.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    return signature.hex()


def verify_signature(public_key_hex: str, message: str, signature_hex: str) -> bool:
    """Verify a DER signature hex against a public key and message."""
    try:
        public_bytes = bytes.fromhex(public_key_hex)
        x = int.from_bytes(public_bytes[:32], "big")
        y = int.from_bytes(public_bytes[32:], "big")
        public_key = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256K1()).public_key()
        public_key.verify(
            bytes.fromhex(signature_hex),
            message.encode("utf-8"),
            ec.ECDSA(hashes.SHA256()),
        )
        return True
    except (ValueError, InvalidSignature):
        return False
