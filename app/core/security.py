from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)


_password_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(
    password_hash: str,
    plain_password: str,
) -> bool:
    try:
        return _password_hasher.verify(
            password_hash,
            plain_password,
        )

    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
    ):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _password_hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return False


def normalize_next_url(value: str | None) -> str:
    if not value:
        return "/"

    if not value.startswith("/"):
        return "/"

    if value.startswith("//"):
        return "/"

    return value
