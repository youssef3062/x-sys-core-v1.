"""Emergency offline token signing and verification helpers.

Design notes:
- Uses Ed25519 (asymmetric) so verifiers only need a public key.
- Encodes a compact JWS-like token: base64url(header).base64url(payload).base64url(signature).
- Keeps payload intentionally minimal for privacy + QR size.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


class EmergencyTokenError(ValueError):
    """Raised when token parsing/validation fails."""


@dataclass
class VerificationResult:
    status: str
    payload: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


HEADER = {"alg": "EdDSA", "typ": "JWT", "kid": "emergency-v1"}


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode((encoded + padding).encode("ascii"))


def load_private_key_from_pem(pem: str) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise EmergencyTokenError("Configured emergency private key is not Ed25519")
    return key


def load_public_key_from_pem(pem: str) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(pem.encode("utf-8"))
    if not isinstance(key, Ed25519PublicKey):
        raise EmergencyTokenError("Configured emergency public key is not Ed25519")
    return key


def public_key_to_spki_pem(public_key: Ed25519PublicKey) -> str:
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def sign_emergency_payload(payload: Dict[str, Any], private_key: Ed25519PrivateKey) -> str:
    header_segment = b64url_encode(
        json.dumps(HEADER, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    payload_segment = b64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = private_key.sign(signing_input)
    return f"{header_segment}.{payload_segment}.{b64url_encode(signature)}"


def verify_emergency_token(token: str, public_key: Ed25519PublicKey, now: Optional[int] = None) -> VerificationResult:
    now_epoch = now or int(time.time())
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError:
        return VerificationResult(status="invalid", reason="Malformed token")

    try:
        header = json.loads(b64url_decode(header_segment).decode("utf-8"))
        payload = json.loads(b64url_decode(payload_segment).decode("utf-8"))
        signature = b64url_decode(signature_segment)
    except Exception:
        return VerificationResult(status="invalid", reason="Malformed token encoding")

    if header.get("alg") != "EdDSA":
        return VerificationResult(status="invalid", reason="Unsupported alg")

    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    try:
        public_key.verify(signature, signing_input)
    except InvalidSignature:
        return VerificationResult(status="invalid", reason="Signature mismatch")

    exp = payload.get("exp")
    if not isinstance(exp, int):
        return VerificationResult(status="invalid", reason="exp missing")
    if exp <= now_epoch:
        return VerificationResult(status="expired", payload=payload, reason="Token expired")

    return VerificationResult(status="verified", payload=payload)
