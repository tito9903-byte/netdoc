from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)


_password_hasher = PasswordHasher()


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


def normalize_next_url(value: str | None) -> str:
    if not value:
        return "/"

    if not value.startswith("/"):
        return "/"

    if value.startswith("//"):
        return "/"

    return value
