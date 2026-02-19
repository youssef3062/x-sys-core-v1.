"""Password hashing utilities with bcrypt-first strategy.

If bcrypt is unavailable in the runtime, we fallback to Werkzeug hashes so
existing deployments/tests still work.
"""

from __future__ import annotations

from werkzeug.security import check_password_hash, generate_password_hash

try:
    import bcrypt  # type: ignore
except Exception:  # pragma: no cover
    bcrypt = None


def hash_password(password: str) -> str:
    if bcrypt:
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
        return hashed.decode("utf-8")
    return generate_password_hash(password, method="scrypt")


def verify_password(password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    if bcrypt and hashed_password.startswith("$2"):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
        except ValueError:
            return False
    return check_password_hash(hashed_password, password)
