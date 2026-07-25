"""Inicializa un entorno seguro antes de importar el resto de la suite.

`unittest discover` importa los archivos en orden alfabético. Este módulo debe
mantener el prefijo `test_000_` para asegurar que la base de desarrollo nunca
sea utilizada por las pruebas automatizadas.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path


_TEST_DIRECTORY = Path(tempfile.mkdtemp(prefix="netdoc-unittest-"))
_TEST_DATABASE = _TEST_DIRECTORY / "netdoc-tests.db"

# Se asignan directamente, no con setdefault, para que una ejecución iniciada
# desde un checkout con `.env` de desarrollo continúe usando datos desechables.
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DATABASE}"
os.environ["NETBOX_URL"] = "https://netbox.invalid"
os.environ["NETBOX_TOKEN"] = "test-token"
os.environ["NETBOX_TOKEN_TYPE"] = "token"
os.environ["NETBOX_VERIFY_SSL"] = "false"
os.environ["NETBOX_WRITE_ENABLED"] = "false"
os.environ["SESSION_SECRET"] = "test-session-secret"
os.environ["SESSION_COOKIE_NAME"] = "netdoc_test_session"
os.environ["ADMIN_USERNAME"] = "admin"


def _cleanup() -> None:
    shutil.rmtree(_TEST_DIRECTORY, ignore_errors=True)


atexit.register(_cleanup)
