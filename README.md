# NetDoc

NetDoc simplifica la consulta, creación guiada y visualización de infraestructura de red mediante NetBox como fuente oficial del inventario técnico. Su objetivo es reducir pasos repetitivos sin sustituir el modelo de datos ni las validaciones de NetBox.

## Estado y funcionalidades

El estado oficial está en [PROJECT_STATUS](docs/PROJECT_STATUS.md).

La versión `0.10.0` fue promovida a `main` y contiene:

- dashboard, dispositivos, interfaces, conexiones e IPAM;
- autenticación multiusuario, roles, permisos, perfil y auditoría;
- búsqueda global y estado del sistema;
- fabricantes, modelos, plantillas de puertos e imágenes;
- creación guiada de modelos, equipos y racks;
- racks 2D/3D con ocupación basada en `u_height`;
- persistencia local versionada con Alembic;
- planes seguros y vista previa de conexiones para el futuro asistente.

`develop` ya incluye la versión `0.10.1` con imágenes frontal y trasera almacenadas por NetDoc. La rama `feature/rack-datacenter-report` agrega:

- vista 3D estilo datacenter disponible únicamente dentro de cada rack;
- escalas **Ajustar** y **Detalle** para equipos de 1U;
- fotografías sin deformación en 2D y 3D;
- reemplazo explícito de la imagen frontal, trasera o ambas;
- revalidación inmediata después de sustituir una imagen;
- reporte PDF descargable con elevación e inventario paginado.

Esta rama debe validarse primero en desarrollo, puerto 8101, antes de fusionarse.

## Principios de producto

1. **NetBox sigue siendo la fuente oficial.** NetDoc no mantiene una copia paralela del inventario técnico.
2. **Los flujos frecuentes deben requerir menos pasos.** Modelos, interfaces, racks, pools y conexiones se presentan como procesos guiados.
3. **Documentar una vez y reutilizar.** Los modelos, imágenes y componentes se definen antes de crear equipos.
4. **La ubicación debe ser explícita.** Sitio, localidad, rack, cara y posición U forman parte del alta física.
5. **La capacidad debe ser visible.** Los pools IP y racks muestran disponibilidad o declaran claramente cuando no puede calcularse.
6. **Las escrituras hacia NetBox son controladas.** Autenticación, permiso, CSRF, auditoría y `NETBOX_WRITE_ENABLED=true` son obligatorios.
7. **Los datos propios permanecen separados.** Cuentas, auditoría e imágenes locales pertenecen a NetDoc; el inventario pertenece a NetBox.
8. **La IA no ejecuta HTTP libre.** Interpreta intención; resolutores, planificadores y políticas deterministas construyen el cambio.
9. **Todo cambio se revisa.** El usuario confirma la huella del plan exacto que será ejecutado.

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
NetBox REST / base local de NetDoc / métricas Linux
```

NetDoc usa Python, FastAPI, Jinja2, HTTPX, Pydantic Settings, SessionMiddleware, Argon2, SQLAlchemy, Alembic, Uvicorn, HTML, CSS y JavaScript.

NetBox mantiene dispositivos, componentes, racks, cables e IPAM. La base configurable de NetDoc conserva:

- usuarios, roles y permisos;
- auditoría;
- imágenes frontal y trasera asociadas a tipos de dispositivo.

Los reportes PDF se generan en memoria mediante primitivas internas y no se guardan permanentemente.

Consulte [arquitectura](docs/ARCHITECTURE.md), [escrituras seguras](docs/NETBOX_WRITE_SAFETY.md) y [racks, imágenes y reportes](docs/RACKS_AND_DEVICE_IMAGES.md).

## Fundamento de cambios seguros

- `app/services/change_plan.py`: pasos, huella y confirmación.
- `app/services/netbox_capabilities.py`: lista cerrada de operaciones conocidas.
- `app/services/netbox_schema_service.py`: descubrimiento `OPTIONS` y validación dinámica.
- `app/services/cable_planner.py`: planificador determinista de cables.
- `POST /api/change-plans/cable`: vista previa de un plan; nunca escribe.

La primera etapa no admite `DELETE`. La IA futura podrá preparar operaciones, pero solo las capacidades explícitamente habilitadas podrán ejecutarse después de validación y confirmación.

## Estructura

- `app/main.py`: aplicación, middleware y rutas base.
- `app/core`: configuración, sesiones, seguridad, autorización, base y migraciones.
- `app/models`: entidades persistentes propias de NetDoc.
- `app/routers`: rutas web, API y flujos guiados.
- `app/services`: reglas, planes, reportes e integración NetBox.
- `app/templates` y `app/static`: interfaz.
- `migrations`: revisiones Alembic del esquema local.
- `tests`: pruebas automatizadas.
- `scripts`: despliegue controlado.
- `docs`: conocimiento versionado.

## Persistencia y migraciones

`DATABASE_URL` selecciona la base de NetDoc. El valor inicial es `sqlite:///./data/netdoc.db`; desarrollo y producción deben usar bases independientes.

La cabeza Alembic actual es `20260725_0002`:

- `20260724_0001`: cuentas, roles, permisos y auditoría;
- `20260725_0002`: imágenes de modelos.

Durante el arranque:

- una base vacía recibe todas las migraciones;
- una base con `alembic_version` se actualiza hasta `head`;
- una base heredada completa del esquema inicial se marca en `20260724_0001` y luego se actualiza;
- un esquema parcial provoca un error de arranque.

Antes de una migración debe respaldarse la base. Desde `0.10.1`, ese respaldo también conserva las imágenes. El rollback de código no revierte ni restaura automáticamente el archivo de datos.

## Entornos y ramas

`feature/*` se crea desde `develop`; se abre PR a `develop`, se prueba en 8101 y después se promueve mediante otro PR hacia `main`. Producción usa 8100. No programe directamente en `main` ni modifique producción manualmente.

Desarrollo y producción deben usar `.env`, cookie de sesión y base independientes. El entorno manual de desarrollo puede usar `NETBOX_WRITE_ENABLED=true` para validar creaciones y modificaciones antes de producción. Las pruebas automatizadas siempre reemplazan esa configuración por `NETBOX_WRITE_ENABLED=false`, usan una base temporal y nunca deben escribir en NetBox.

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

No ejecute directamente la suite desde un checkout con el `.env` de desarrollo o producción. El ejecutor aislado crea una base temporal, mantiene las escrituras hacia NetBox deshabilitadas y elimina los datos de prueba.

No versionar `.env`, bases, tokens, contraseñas, hashes, secretos de sesión o claves. Para despliegues consulte [DEPLOYMENT](docs/DEPLOYMENT.md); `git push` no despliega al servidor.

## Documentación

[Índice](docs/README.md) · [Estado](docs/PROJECT_STATUS.md) · [Roadmap](docs/ROADMAP.md) · [Integración NetBox](docs/NETBOX_INTEGRATION.md) · [Escrituras seguras](docs/NETBOX_WRITE_SAFETY.md) · [Cobertura de módulos](docs/NETBOX_MODULE_COVERAGE.md) · [Arquitectura IA](docs/AI_ASSISTANT_ARCHITECTURE.md) · [Racks, imágenes y reportes](docs/RACKS_AND_DEVICE_IMAGES.md) · [Pruebas](docs/TESTING.md) · [Seguridad](docs/SECURITY.md) · [ADR](docs/adr/README.md).
