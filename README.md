# NetDoc

NetDoc simplifica la consulta, creación guiada y visualización de infraestructura de red mediante NetBox como fuente oficial del inventario técnico. Su objetivo es reducir los pasos repetitivos de NetBox sin duplicar ni sustituir su modelo de datos.

## Estado y funcionalidades

El estado oficial está en [PROJECT_STATUS](docs/PROJECT_STATUS.md). `develop` incluye:

- dashboard, dispositivos, interfaces, conexiones y racks 2D;
- autenticación multiusuario, roles, permisos y auditoría;
- perfil de autoservicio y protección temporal de login;
- búsqueda global y estado del sistema;
- persistencia local versionada con Alembic;
- desarrollo y producción separados con despliegue controlado.

La rama `feature/documentation-workflows-ui`, presentada en el PR #4 hacia `develop`, incorpora para revisión:

- navegación organizada por procesos de documentación;
- dashboard como punto de inicio operativo;
- direccionamiento IP con prefijos, pools, localidad, VRF, capacidad y disponibilidad;
- modelos de dispositivo con generación masiva de interfaces mediante patrones;
- carga opcional de imágenes frontal y trasera durante la creación del modelo;
- administración posterior de imágenes;
- creación guiada de racks y mejoras en la instalación física;
- ocupación basada en `u_height`, incluida media unidad y equipos 0U;
- elevación 2D y vista física 3D que reutilizan las imágenes del modelo;
- planes inmutables para preparar escrituras seguras hacia NetBox;
- lista cerrada de capacidades y rechazo inicial de eliminaciones automáticas;
- descubrimiento de campos y opciones mediante `OPTIONS`;
- planificador de cables y API de vista previa sin escritura;
- documentación de cobertura de módulos y arquitectura del futuro asistente.

Esta rama es la versión `0.10.0`, permanece como borrador y debe validarse únicamente en desarrollo, puerto 8101, antes de fusionarse.

## Principios de producto

1. **NetBox sigue siendo la fuente oficial.** NetDoc no mantiene una copia paralela del inventario.
2. **Los flujos frecuentes deben requerir menos pasos.** Modelos, interfaces, racks, pools y conexiones se presentan como procesos guiados.
3. **Documentar una vez y reutilizar.** Los tipos de dispositivo, sus imágenes y componentes se definen antes de crear equipos.
4. **La ubicación debe ser explícita.** Sitio, localidad, rack, cara y posición U forman parte del alta física.
5. **La capacidad debe ser visible.** Los pools IP y racks muestran disponibilidad real o declaran claramente cuando no puede calcularse.
6. **Las escrituras son controladas.** Autenticación, permiso, CSRF, auditoría y `NETBOX_WRITE_ENABLED=true` son obligatorios.
7. **La IA no ejecuta HTTP libre.** Interpreta la intención; resolutores, planificadores y políticas deterministas construyen el cambio.
8. **Todo cambio se revisa.** El usuario confirma la huella del plan exacto que será ejecutado.

## Arquitectura y tecnologías

```text
Navegador / futuro chat
        ↓
FastAPI + Jinja2
        ↓
Resolutores y planes seguros
        ↓
Servicios deterministas
        ↓
NetBox REST / base local / métricas Linux
```

NetDoc usa Python, FastAPI, Jinja2, HTTPX, Pydantic Settings, SessionMiddleware, Argon2, SQLAlchemy, Alembic, Uvicorn, HTML, CSS y JavaScript. NetBox mantiene dispositivos, componentes, racks, cables e IPAM; una base propia configurable conserva únicamente usuarios, roles, permisos y auditoría. Consulte [arquitectura](docs/ARCHITECTURE.md) y [escrituras seguras](docs/NETBOX_WRITE_SAFETY.md).

## Fundamento de cambios seguros

- `app/services/change_plan.py`: pasos, huella y confirmación.
- `app/services/netbox_capabilities.py`: allowlist de operaciones conocidas.
- `app/services/netbox_schema_service.py`: descubrimiento `OPTIONS` y validación dinámica.
- `app/services/cable_planner.py`: planificador determinista de cables.
- `POST /api/change-plans/cable`: vista previa de un plan; nunca escribe.

La primera etapa no admite `DELETE`. La IA futura podrá preparar muchas operaciones, pero solo las capacidades explícitamente habilitadas podrán ejecutarse después de validación y confirmación.

## Estructura

- `app/main.py`: aplicación, middleware y rutas base.
- `app/core`: configuración, sesiones, seguridad, autorización, base y migraciones.
- `app/models`: entidades persistentes propias de NetDoc.
- `app/routers`: rutas web, API y flujos guiados.
- `app/services`: reglas, planes e integración NetBox.
- `app/templates` y `app/static`: interfaz.
- `migrations`: revisiones Alembic del esquema local.
- `tests`: pruebas automatizadas.
- `scripts`: despliegue controlado.
- `docs`: conocimiento versionado.

## Persistencia y migraciones

`DATABASE_URL` selecciona la base de NetDoc. El valor inicial es `sqlite:///./data/netdoc.db`; desarrollo y producción deben usar archivos o motores independientes.

Durante el arranque, NetDoc ejecuta Alembic hasta `head`:

- una base vacía recibe la migración inicial;
- una base heredada completa se marca en `head` sin borrar datos;
- una base versionada se actualiza;
- un esquema parcial provoca un error de arranque.

Antes de una migración debe respaldarse la base. El rollback de código no revierte ni restaura automáticamente el archivo de datos.

## Entornos y ramas

`feature/*` se crea desde `develop`; se abre PR a `develop`, se prueba en 8101 y después se promueve mediante otro PR hacia `main`. Producción usa 8100. No programe directamente en `main` ni modifique producción manualmente.

Desarrollo y producción deben usar `.env`, cookie de sesión y base independientes. Desarrollo debe conservar `NETBOX_WRITE_ENABLED=false`.

## Inicio rápido local

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
cp .env.example .env
.venv/bin/alembic heads
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8101
```

Validaciones principales:

```bash
scripts/netdoc-test-isolated
python -m compileall -q app tests migrations
python -c 'from app.main import app; print(app.title, len(app.routes))'
```

No ejecute directamente la suite desde un checkout con el `.env` de desarrollo o producción. El ejecutor aislado crea una base temporal, mantiene escritura deshabilitada y elimina los datos de prueba.

No versionar `.env`, bases, tokens, contraseñas, hashes, secretos de sesión o claves. Para despliegues consulte [DEPLOYMENT](docs/DEPLOYMENT.md); `git push` no despliega al servidor.

## Documentación

[Índice](docs/README.md) · [Estado](docs/PROJECT_STATUS.md) · [Roadmap](docs/ROADMAP.md) · [Integración NetBox](docs/NETBOX_INTEGRATION.md) · [Escrituras seguras](docs/NETBOX_WRITE_SAFETY.md) · [Cobertura de módulos](docs/NETBOX_MODULE_COVERAGE.md) · [Arquitectura IA](docs/AI_ASSISTANT_ARCHITECTURE.md) · [Racks e imágenes](docs/RACKS_AND_DEVICE_IMAGES.md) · [Pruebas](docs/TESTING.md) · [Seguridad](docs/SECURITY.md) · [ADR](docs/adr/README.md).
