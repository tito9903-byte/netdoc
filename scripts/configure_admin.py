from getpass import getpass
from pathlib import Path
import secrets

from argon2 import PasswordHasher


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_DIRECTORY / ".env"


def update_env_file(
    path: Path,
    values: dict[str, str],
) -> None:
    lines = []

    if path.exists():
        lines = path.read_text(
            encoding="utf-8",
        ).splitlines()

    output = []
    updated_keys = set()

    for line in lines:
        stripped = line.strip()

        if (
            not stripped
            or stripped.startswith("#")
            or "=" not in line
        ):
            output.append(line)
            continue

        key = line.split("=", 1)[0].strip()

        if key in values:
            output.append(f"{key}={values[key]}")
            updated_keys.add(key)
        else:
            output.append(line)

    if output and output[-1].strip():
        output.append("")

    for key, value in values.items():
        if key not in updated_keys:
            output.append(f"{key}={value}")

    path.write_text(
        "\n".join(output).rstrip() + "\n",
        encoding="utf-8",
    )

    path.chmod(0o600)


def main() -> None:
    print("Configuración del administrador de NetDoc")
    print()

    username = input(
        "Usuario administrador [lgarcia]: "
    ).strip()

    if not username:
        username = "lgarcia"

    while True:
        password = getpass("Contraseña: ")
        confirmation = getpass("Confirmar contraseña: ")

        if password != confirmation:
            print("Las contraseñas no coinciden.")
            print()
            continue

        if len(password) < 10:
            print(
                "La contraseña debe tener al menos "
                "10 caracteres."
            )
            print()
            continue

        break

    password_hash = PasswordHasher().hash(password)
    session_secret = secrets.token_urlsafe(64)

    update_env_file(
        ENV_FILE,
        {
            "ADMIN_USERNAME": username,
            "ADMIN_PASSWORD_HASH": password_hash,
            "SESSION_SECRET": session_secret,
            "SESSION_COOKIE_SECURE": "false",
            "SESSION_MAX_AGE": "28800",
        },
    )

    print()
    print("Administrador configurado correctamente.")
    print(f"Usuario: {username}")
    print(f"Archivo protegido: {ENV_FILE}")
    print("La contraseña no fue almacenada en texto plano.")


if __name__ == "__main__":
    main()
