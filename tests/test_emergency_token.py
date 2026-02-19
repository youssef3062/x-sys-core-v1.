import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.security.emergency_token import sign_emergency_payload, verify_emergency_token


def test_sign_and_verify_emergency_token():
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    payload = {
        "qr_id": "BRESCAN-0001",
        "full_name": "Jane Roe",
        "age": 42,
        "iat": int(time.time()),
        "exp": int(time.time()) + 120,
    }

    token = sign_emergency_payload(payload, private_key)
    result = verify_emergency_token(token, public_key)

    assert result.status == "verified"
    assert result.payload["qr_id"] == "BRESCAN-0001"


def test_expired_emergency_token():
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    payload = {
        "qr_id": "BRESCAN-0002",
        "full_name": "John Doe",
        "age": 61,
        "iat": 10,
        "exp": 11,
    }

    token = sign_emergency_payload(payload, private_key)
    result = verify_emergency_token(token, public_key, now=100)

    assert result.status == "expired"
