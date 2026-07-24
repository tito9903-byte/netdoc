# NetDoc

NetDoc simplifica la consulta, creación guiada y visualización de infraestructura de red mediante NetBox como fuente oficial del inventario técnico.

## Estado y funcionalidades

El estado oficial está en [PROJECT_STATUS](docs/PROJECT_STATUS.md). El código estable incluye dashboard, dispositivos con búsqueda/filtros/paginación/detalle e interfaces, creación guiada, conexiones y cables, racks 2D y despliegue separado por entorno.

La rama `feature/access-control-audit` incorpora para revisión:

- autenticación multiusuario;
- roles Administrador, Operador y Consulta;
- permisos por módulo;
- creación y edición de usuarios;
- activación de cuentas y restablecimiento de contraseña;
- creación y edición de roles;
- auditoría de accesos y cambios;
- navegación y rutas protegidas por permiso.

## Arquitectura y tecnologías

`Navegador → FastAPI/Jinja2 → servicios → NetBox REST`

NetDoc usa Python, FastAPI, Jinja2, HTTPX, Pydantic Settings, SessionMiddleware, Argon2, SQLAlchemy, Uvicorn, HTML, CSS y JavaScript. NetBox mantiene el inventario; una base propia configurable conserva únicamente usuarios, roles, permisos y auditoría. Consulte [arquitectura](docs/ARCHITECTURE.md).

## Estructura

- `app/main.py`: aplicación, middleware y rutas base.
- `app/core`: configuración, sesiones, seguridad, autorización y base de datos.
- `app/models`: entidades persistentes propias de NetDoc.
- `app/routers`: rutas web y API.
- `app/services`: reglas de negocio e integración NetBox.
- `app/templates` y `app/static`: interfaz.
- `tests`: pruebas automatizadas.
- `scripts`: despliegue controlado.
- `docs`: conocimiento versionado.

## Entornos y ramas

`feature/*` se crea desde `develop`; PR a `develop`, prueba en el puerto 8101 y promoción posterior a `main`. Producción usa 8100. No programe en `main` ni modifique producción manualmente.

Desarrollo y producción deben usar `.env`, cookie de sesión y base de datos independientes. El valor predeterminado de persistencia es `sqlite:///./data/netdoc.db`; `DATABASE_URL` permite seleccionar otro motor.

## Inicio rápido local

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env  # sustituya solo en su entorno los marcadores seguros
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8101
```

Pruebas actuales:

```bash
python -m unittest tests.test_access_control -v
```

No versionar `.env`, bases de datos, tokens, contraseñas, hashes, secretos de sesión o claves. Para despliegues controlados consulte [DEPLOYMENT](docs/DEPLOYMENT.md); `git push` no despliega al servidor.

## Documentación

[Índice](docs/README.md) · [Estado](docs/PROJECT_STATUS.md) · [Operaciones](docs/OPERATIONS.md) · [Seguridad](docs/SECURITY.md) · [Roadmap](docs/ROADMAP.md) · [Pruebas](docs/TESTING.md) · [NetBox](docs/NETBOX_INTEGRATION.md) · [ADR](docs/adr/README.md) · [Contribución](CONTRIBUTING.md) · [Handoff IA](docs/AI_HANDOFF_PROMPT.md).
