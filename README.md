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

- una navegación organizada por procesos de documentación;
- un dashboard como punto de inicio operativo;
- direccionamiento IP con prefijos, pools, localidad, VRF, capacidad y disponibilidad;
- modelos de dispositivo con generación masiva de interfaces mediante patrones;
- carga opcional de imágenes frontal y trasera durante la creación del modelo;
- administración posterior de las imágenes del modelo;
- creación guiada de racks y mejoras en la instalación física de equipos;
- ocupación basada en la altura `u_height` real, incluida media unidad y equipos 0U;
- elevación 2D y vista física 3D que reutilizan las imágenes del modelo;
- correcciones visuales en racks, conexiones, búsqueda y administración;
- foco visible, controles mayores y comportamiento accesible del menú móvil.

Esta rama es la versión `0.10.0`, permanece como borrador y no está desplegada todavía. Debe validarse únicamente en desarrollo, puerto 8101, antes de fusionarse.

## Principios de producto

1. **NetBox sigue siendo la fuente oficial.** NetDoc no mantiene una copia paralela del inventario.
2. **Los flujos frecuentes deben requerir menos pasos.** Modelos, interfaces, racks, pools y conexiones se presentan como procesos guiados.
3. **Documentar una vez y reutilizar.** Los tipos de dispositivo, sus imágenes y sus componentes se definen antes de crear equipos.
4. **La ubicación debe ser explícita.** Sitio, localidad, rack, cara y posición U deben formar parte del alta física.
5. **La capacidad debe ser visible.** Los pools IP y racks deben mostrar disponibilidad real o declarar claramente cuando todavía no está calculada.
6. **Las escrituras son controladas.** Autenticación, permiso, CSRF, auditoría y `NETBOX_WRITE_ENABLED=true` son obligatorios.

## Arquitectura y tecnologías

`Navegador → FastAPI/Jinja2 → servicios → NetBox REST / base local / métricas Linux`

NetDoc usa Python, FastAPI, Jinja2, HTTPX, Pydantic Settings, SessionMiddleware, Argon2, SQLAlchemy, Alembic, Uvicorn, HTML, CSS y JavaScript. NetBox mantiene dispositivos, componentes, racks, cables e IPAM; una base propia configurable conserva únicamente usuarios, roles, permisos y auditoría. Consulte [arquitectura](docs/ARCHITECTURE.md).

## Estructura

- `app/main.py`: aplicación, middleware y rutas base.
- `app/core`: configuración, sesiones, seguridad, autorización, base de datos y migraciones.
- `app/models`: entidades persistentes propias de NetDoc.
- `app/routers`: rutas web, API y flujos guiados.
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
- una base heredada completa se marca en `head` sin borrar datos;
- una base versionada se actualiza;
- un esquema parcial provoca un error de arranque.

Antes de una migración debe respaldarse la base. El rollback de código no revierte ni restaura automáticamente el archivo de datos.

## Entornos y ramas

`feature/*` se crea desde `develop`; se abre PR a `develop`, se prueba en 8101 y después se promueve mediante otro PR hacia `main`. Producción usa 8100. No programe directamente en `main` ni modifique producción manualmente.

Desarrollo y producción deben usar `.env`, cookie de sesión y base de datos independientes. Desarrollo debe conservar `NETBOX_WRITE_ENABLED=false`.

## Inicio rápido local

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
cp .env.example .env  # sustituya solo en su entorno los marcadores seguros
.venv/bin/alembic heads
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8101
```

Validaciones principales:

```bash
scripts/netdoc-test-isolated
python -m compileall -q app tests migrations
python -c 'from app.main import app; print(app.title, len(app.routes))'
```

No ejecute directamente la suite desde un checkout que contenga el `.env` de desarrollo o producción. El ejecutor aislado crea una base temporal, mantiene escritura deshabilitada y elimina los datos de prueba al terminar.

GitHub Actions valida dependencias, compilación, grafo Alembic, pruebas, importación, plantillas y scripts. Las pruebas contra NetBox real, cargas multipart y systemd se realizan únicamente en el servidor autorizado.

No versionar `.env`, bases de datos, tokens, contraseñas, hashes, secretos de sesión o claves. Para despliegues controlados consulte [DEPLOYMENT](docs/DEPLOYMENT.md); `git push` no despliega al servidor.

## Documentación

[Índice](docs/README.md) · [Estado](docs/PROJECT_STATUS.md) · [Operaciones](docs/OPERATIONS.md) · [Seguridad](docs/SECURITY.md) · [Roadmap](docs/ROADMAP.md) · [Pruebas](docs/TESTING.md) · [NetBox](docs/NETBOX_INTEGRATION.md) · [Racks e imágenes](docs/RACKS_AND_DEVICE_IMAGES.md) · [ADR](docs/adr/README.md) · [Contribución](CONTRIBUTING.md) · [Handoff IA](docs/AI_HANDOFF_PROMPT.md).