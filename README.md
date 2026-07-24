# NetDoc

NetDoc simplifica la consulta, creación guiada y visualización de infraestructura
de red mediante NetBox como fuente oficial del inventario técnico.

## Estado y funcionalidades

El estado oficial está en [PROJECT_STATUS](docs/PROJECT_STATUS.md). El código
incluye autenticación administrativa inicial, dashboard, dispositivos con
búsqueda/filtros/paginación/detalle e interfaces, creación guiada, conexiones y
cables, y racks 2D con detalle. El próximo objetivo planificado es usuarios,
roles, permisos y auditoría.

## Arquitectura y tecnologías

Navegador → FastAPI/Jinja2 → servicios HTTPX → API REST de NetBox. Usa Python,
FastAPI, Jinja2, HTTPX, Pydantic Settings, SessionMiddleware, Argon2, Uvicorn,
HTML, CSS y JavaScript. Consulte [arquitectura](docs/ARCHITECTURE.md).

## Estructura

`app/main.py` inicia la aplicación; `app/core` configuración/seguridad;
`app/routers` rutas; `app/services` NetBox; `app/templates` y `app/static` UI;
`scripts` despliegue; `docs` conocimiento versionado.

## Entornos y ramas

`feature/*` se crea desde `develop`; PR a `develop`, prueba de desarrollo y
promoción posterior a `main`. Desarrollo usa 8101 y producción 8100 en
entornos separados. No programe en `main` ni modifique producción manualmente.

## Inicio rápido local

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env  # sustituya solo en su entorno los marcadores seguros
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8101
```

No versionar `.env`, tokens, contraseñas, hashes, secretos de sesión o claves.
Para despliegues controlados consulte [DEPLOYMENT](docs/DEPLOYMENT.md), no use
`git push` como sustituto de despliegue.

## Documentación

[Índice](docs/README.md) · [Estado](docs/PROJECT_STATUS.md) ·
[Operaciones](docs/OPERATIONS.md) · [Seguridad](docs/SECURITY.md) ·
[Roadmap](docs/ROADMAP.md) · [Pruebas](docs/TESTING.md) ·
[NetBox](docs/NETBOX_INTEGRATION.md) · [ADR](docs/adr/README.md) ·
[Contribución](CONTRIBUTING.md) · [Handoff IA](docs/AI_HANDOFF_PROMPT.md).
