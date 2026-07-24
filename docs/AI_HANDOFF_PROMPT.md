# Prompt maestro de continuidad de NetDoc

Copia este documento completo en una conversación nueva para continuar el proyecto sin depender de conversaciones anteriores.

## Contexto general

Estás continuando el desarrollo de **NetDoc**, una plataforma web independiente para consultar, crear y visualizar documentación de infraestructura de red. NetBox es la fuente oficial del inventario técnico; NetDoc simplifica la experiencia operativa y mantiene solamente su identidad, permisos y auditoría internos.

- Repositorio: `tito9903-byte/netdoc`
- Responsable: Luis Emilio García Pichardo
- Servidor dedicado de NetDoc: `192.168.10.93`
- Sistema operativo: Ubuntu 24.04
- NetBox: `https://192.168.10.95`
- NetBox documentado: versión 4.4.2

NetDoc es la única aplicación de este proyecto alojada en ese servidor. No inventes integraciones ni relaciones con otros sistemas.

## Entornos

### Desarrollo

- Ruta: `/opt/netdoc-dev`
- Rama estable del entorno: `develop`
- Servicio: `netdoc-dev`
- Puerto: `8101`
- URL: `http://192.168.10.93:8101`
- Cookie: `netdoc_dev_session`
- Escritura NetBox: `NETBOX_WRITE_ENABLED=false`
- Script instalado y probado por el propietario: `/usr/local/sbin/netdoc-deploy-dev`

### Producción

- Ruta: `/opt/netdoc-prod`
- Rama: `main`
- Servicio: `netdoc-prod`
- Puerto: `8100`
- URL: `http://192.168.10.93:8100`
- Escritura NetBox: controlada mediante `.env`
- Script instalado y probado por el propietario: `/usr/local/sbin/netdoc-deploy-prod`

### Respaldo temporal

- Ruta: `/opt/netbox-documental`
- No es producción activa.
- No debe eliminarse ni reutilizarse sin decisión operativa explícita.

El propietario verificó manualmente ambos servicios y scripts el 2026-07-24; desarrollo y producción terminaron activos y `/login` respondió HTTP 200. Esta evidencia no significa que un agente de IA tenga acceso al servidor.

## Flujo Git obligatorio

- `main`: producción.
- `develop`: desarrollo integrado.
- `feature/*`: trabajo aislado creado desde `develop`.
- Abrir PR de `feature/*` hacia `develop`.
- Revisar y probar en 8101.
- Promover mediante otro PR de `develop` hacia `main`.
- No programar directamente en `main`.
- No fusionar automáticamente.
- `git push` no despliega al servidor.

Trabajo actual:

- Rama: `feature/access-control-audit`
- Objetivo: usuarios, roles, permisos y auditoría.
- Estado: implementación amplia creada y pendiente de revisión, PR y prueba manual en desarrollo.
- No afirmar que esta rama está desplegada.

## Arquitectura y tecnologías

Flujo de inventario:

`Navegador → FastAPI/Jinja2 → servicios HTTPX → API REST de NetBox`

Flujo interno:

`FastAPI → SQLAlchemy → base propia de NetDoc`

Tecnologías:

- Python
- FastAPI
- Jinja2
- HTTPX
- Pydantic Settings
- SessionMiddleware
- Argon2
- SQLAlchemy
- SQLite por defecto, configurable mediante `DATABASE_URL`
- Uvicorn
- HTML, CSS y JavaScript
- systemd
- Git y GitHub

Estructura:

- `app/main.py`: aplicación, middleware, autenticación y rutas base.
- `app/core/config.py`: configuración.
- `app/core/security.py`: Argon2.
- `app/core/auth.py`: sesión, permisos, CSRF y middleware.
- `app/core/database.py`: motor y sesiones SQLAlchemy.
- `app/models/access.py`: usuarios, roles, permisos y auditoría.
- `app/services/access_service.py`: reglas de identidad y autorización.
- `app/services/`: integración NetBox y servicios especializados.
- `app/routers/admin.py`: administración de acceso.
- `app/routers/`: dispositivos, conexiones y racks.
- `app/templates/`: vistas Jinja2.
- `app/static/`: CSS, JavaScript e imágenes.
- `tests/`: pruebas automatizadas.
- `scripts/`: despliegue controlado.
- `docs/`: documentación viva.
- `.env`: configuración sensible; nunca se versiona ni se imprime.

## Datos y límites

NetBox conserva:

- dispositivos;
- interfaces;
- racks;
- cables;
- sitios y demás inventario técnico.

La base de NetDoc conserva únicamente:

- usuarios;
- roles;
- permisos;
- relaciones rol-permiso;
- eventos de auditoría.

Valor inicial:

`DATABASE_URL=sqlite:///./data/netdoc.db`

Cada entorno debe usar su propia base. `data/`, `*.db`, `*.sqlite` y `*.sqlite3` están ignorados. La primera versión crea el esquema automáticamente; cualquier modificación posterior requiere migraciones Alembic.

## Funcionalidades estables

- Dashboard conectado a NetBox.
- Dispositivos con listado, búsqueda, filtros y paginación.
- Detalle de dispositivo e interfaces.
- Creación guiada de equipos.
- Consulta y creación de conexiones/cables.
- Listado y visualización 2D de racks.
- Inspector de equipos del rack.
- Integración REST con NetBox.
- Separación de desarrollo y producción.
- Scripts de despliegue con `flock`, validaciones, reintentos y rollback.

## Módulo actual implementado en la rama

- Autenticación multiusuario persistente.
- Bootstrap del primer administrador desde `ADMIN_USERNAME` y `ADMIN_PASSWORD_HASH`.
- Roles iniciales Administrador, Operador y Consulta.
- Nueve permisos por módulo.
- Creación y edición de usuarios.
- Activación/desactivación de cuentas.
- Asignación de rol.
- Restablecimiento de contraseña.
- Creación y edición de roles personalizados.
- Protección de roles del sistema.
- Protección para conservar un administrador activo.
- Navegación condicionada por permisos.
- Autorización en servidor para HTML y API.
- Pantalla 403.
- Auditoría de login correcto/fallido, logout, usuarios, roles y solicitudes de creación de inventario.
- Filtros y paginación básica de auditoría.
- Pruebas unitarias iniciales.

## Validaciones ejecutadas en la rama

Ejecutadas en un entorno aislado, no en el servidor:

- Compilación de sintaxis de módulos Python: correcta.
- Inicialización SQLite en memoria: correcta.
- Creación de nueve permisos y tres roles: correcta.
- Creación y autenticación de usuario de prueba: correcta.
- Carga sintáctica de plantillas Jinja2: correcta.
- `python -m unittest tests.test_access_control -v`: cuatro pruebas superadas.
- Middleware aislado: una solicitud no autenticada a `/` redirigió a `/login`.

No se probaron todavía systemd, 8101, navegador completo, base persistente del servidor ni integración real de esta rama con NetBox.

## Seguridad

- Nunca incluir tokens, contraseñas, hashes, claves ni `.env` en Git o respuestas.
- Las contraseñas se almacenan como hashes Argon2.
- Cuentas nuevas: mínimo 10 caracteres, mayúscula, minúscula y número.
- La seguridad real se aplica en servidor; ocultar menús no sustituye autorización.
- Operaciones administrativas usan CSRF.
- No registrar secretos en auditoría.
- Mantener al menos un administrador activo.
- Desarrollo debe permanecer sin escritura NetBox.
- Rotar el token de NetBox previamente expuesto y reducir sus permisos.
- Respaldar la base antes de migraciones.
- Reevaluar SQLite antes de múltiples workers o alta concurrencia.

## Despliegue

Scripts:

- `netdoc-deploy-dev`: actualiza solo `develop` y 8101.
- `netdoc-deploy-prod`: actualiza solo `main` y 8100; exige `DESPLEGAR` o `--yes`.

Los scripts:

- se ejecutan como root para systemd;
- ejecutan Git, pip y Python como `sshtelenord`;
- validan rama, remoto, `.env`, `.venv`, propietario y árbol limpio;
- rechazan `.env` versionado o no ignorado;
- usan `flock`;
- instalan dependencias;
- compilan e importan la aplicación;
- reinician solo el servicio correcto;
- prueban `/login` con reintentos;
- restauran el commit anterior ante fallos.

No desplegar la rama actual directamente. Primero PR hacia `develop`, revisión, fusión autorizada y luego `netdoc-deploy-dev`.

## Trabajo pendiente inmediato

1. Revisar el diff completo de `feature/access-control-audit`.
2. Confirmar el ADR 0005.
3. Validar importación del repositorio completo.
4. Abrir o revisar PR hacia `develop` sin fusionarlo.
5. Desplegar únicamente en desarrollo después de aprobación.
6. Probar login y navegación con Administrador, Operador y Consulta.
7. Probar usuarios, roles, contraseñas y denegaciones directas por URL.
8. Revisar auditoría correcta/fallida.
9. Verificar permisos del archivo de base y que Git lo ignore.
10. Corregir incidencias antes de cualquier PR hacia `main`.

Después se planifican migraciones Alembic, respaldo/recuperación, revocación inmediata de sesiones, exportación/retención de auditoría, edición controlada de inventario, patch panels, búsqueda global, topologías, 3D, errores centralizados y observabilidad.

## Validaciones obligatorias antes de terminar

- Revisar diff completo.
- `python -m compileall app tests`.
- `python -m unittest tests.test_access_control -v`.
- Importar `app.main`.
- Cargar plantillas Jinja2.
- Validar scripts modificados con `bash -n`.
- Revisar enlaces Markdown.
- Buscar secretos y claves privadas.
- Declarar qué no se pudo probar.
- Actualizar `CHANGELOG.md`, `PROJECT_STATUS.md` y ADR aplicable.

## Archivos que deben leerse primero

1. `AGENTS.md`
2. `docs/PROJECT_STATUS.md`
3. `docs/ARCHITECTURE.md`
4. `docs/SECURITY.md`
5. `docs/TESTING.md`
6. `docs/DEPLOYMENT.md`
7. `docs/OPERATIONS.md`
8. `CONTRIBUTING.md`
9. `docs/adr/README.md` y ADR vigentes
10. `CHANGELOG.md`
11. `docs/ROADMAP.md`

## Información que nunca debe inventarse

- Secretos o contenido de `.env`.
- Acceso al servidor.
- Pruebas o despliegues no ejecutados.
- Funcionalidades no presentes en la rama.
- Estado de una base del servidor no inspeccionada.
- Versiones no verificadas.
- Permisos exactos de NetBox no confirmados.
- Integraciones con proyectos ajenos a NetDoc.

## Formato esperado de respuesta del agente

Indica qué entendiste, archivos revisados y modificados, decisiones, validaciones y resultados reales, limitaciones, pruebas manuales necesarias, documentación actualizada, estado del PR y próximos pasos. Una tarea termina con cambios revisados, documentación coherente, commit y PR correcto sin fusión automática.
