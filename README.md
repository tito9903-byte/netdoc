# NetDoc

NetDoc simplifica la consulta, creación guiada y visualización de infraestructura de red mediante NetBox como fuente oficial del inventario técnico.

## Estado y funcionalidades

El estado oficial está en [PROJECT_STATUS](docs/PROJECT_STATUS.md). El código estable incluye dashboard, dispositivos con búsqueda, filtros, paginación, detalle e interfaces, creación guiada, conexiones y cables, racks 2D y despliegue separado por entorno.

La rama `feature/access-control-audit`, presentada en el PR #3 hacia `develop`, incorpora para revisión:

- autenticación multiusuario persistente con Argon2;
- roles Administrador, Operador y Consulta, además de roles personalizados;
- 11 permisos separados por módulo;
- administración y eliminación controlada de usuarios;
- administración de roles y permisos;
- perfil de autoservicio para nombre, correo y contraseña propia;
- bloqueo temporal configurable tras intentos repetidos de login;
- auditoría con filtros, paginación y exportación CSV;
- búsqueda global de dispositivos, interfaces, racks, sitios y cables;
- módulo Sistema de solo lectura para CPU, RAM, disco, red y uptime;
- navegación, páginas y API protegidas por permiso;
- esquema local versionado con Alembic y migración inicial `20260724_0001`.

Esta rama no está desplegada todavía. Debe probarse únicamente en desarrollo, puerto 8101, antes de considerar `main`.

## Arquitectura y tecnologías

`Navegador → FastAPI/Jinja2 → servicios → NetBox REST / base local / métricas Linux`

NetDoc usa Python, FastAPI, Jinja2, HTTPX, Pydantic Settings, SessionMiddleware, Argon2, SQLAlchemy, Alembic, Uvicorn, HTML, CSS y JavaScript. NetBox mantiene el inventario; una base propia configurable conserva únicamente usuarios, roles, permisos y auditoría. Consulte [arquitectura](docs/ARCHITECTURE.md).

## Estructura

- `app/main.py`: aplicación, middleware y rutas base.
- `app/core`: configuración, sesiones, seguridad, autorización, base de datos y migraciones.
- `app/models`: entidades persistentes propias de NetDoc.
- `app/routers`: rutas web y API.
- `app/services`: reglas de negocio e integración NetBox.
- `app/templates` y `app/static`: interfaz.
- `migrations`: revisiones Alembic del esquema local.
- `tests`: pruebas automatizadas.
- `scripts`: despliegue controlado.
- `docs`: conocimiento versionado.

## Persistencia y migraciones

`DATABASE_URL` selecciona la base de NetDoc. El valor inicial es `sqlite:///./data/netdoc.db`; desarrollo y producción deben usar archivos o motores independientes.

Durante el arranque, NetDoc ejecuta Alembic hasta `head`:

- una base vacía recibe la migración inicial;
- una base heredada con todas las tablas anteriores se marca en `head` sin borrar datos;
- una base ya versionada se actualiza;
- un esquema parcial provoca un error de arranque para no ocultar una instalación dañada.

Antes del primer despliegue de esta rama debe respaldarse la base indicada por `DATABASE_URL`. El rollback de código no revierte ni restaura automáticamente la base.

## Entornos y ramas

`feature/*` se crea desde `develop`; se abre PR a `develop`, se prueba en el puerto 8101 y después se promueve mediante otro PR hacia `main`. Producción usa 8100. No programe directamente en `main` ni modifique producción manualmente.

Desarrollo y producción deben usar `.env`, cookie de sesión y base de datos independientes. Desarrollo debe conservar `NETBOX_WRITE_ENABLED=false`.

## Inicio rápido local

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
cp .env.example .env  # sustituya solo en su entorno los marcadores seguros
.venv/bin/alembic heads
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8101
```

Pruebas y validaciones principales:

```bash
python -m compileall -q app tests migrations
alembic heads
python -m unittest discover -s tests -v
python -c 'from app.main import app; print(app.title, len(app.routes))'
```

La rama registra 41 rutas, 19 plantillas y 27 pruebas automatizadas. GitHub Actions valida dependencias, compilación, grafo Alembic, pruebas, importación, plantillas y scripts.

No versionar `.env`, bases de datos, tokens, contraseñas, hashes, secretos de sesión o claves. Para despliegues controlados consulte [DEPLOYMENT](docs/DEPLOYMENT.md); `git push` no despliega al servidor.

## Documentación

[Índice](docs/README.md) · [Estado](docs/PROJECT_STATUS.md) · [Operaciones](docs/OPERATIONS.md) · [Seguridad](docs/SECURITY.md) · [Roadmap](docs/ROADMAP.md) · [Pruebas](docs/TESTING.md) · [NetBox](docs/NETBOX_INTEGRATION.md) · [ADR](docs/adr/README.md) · [Contribución](CONTRIBUTING.md) · [Handoff IA](docs/AI_HANDOFF_PROMPT.md).