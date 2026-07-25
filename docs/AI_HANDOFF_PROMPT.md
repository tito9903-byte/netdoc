# Prompt maestro de continuidad de NetDoc

Copia este documento completo en una conversación nueva para continuar el proyecto sin depender de conversaciones anteriores.

## Contexto general

Estás continuando el desarrollo de **NetDoc**, una plataforma web independiente para consultar, crear y visualizar documentación de infraestructura de red. NetBox es la fuente oficial del inventario técnico; NetDoc simplifica la experiencia operativa y mantiene solamente usuarios, roles, permisos y auditoría propios.

- Repositorio: `tito9903-byte/netdoc`
- Responsable: Luis Emilio García Pichardo
- Servidor dedicado de NetDoc: `192.168.10.93`
- Sistema operativo: Ubuntu 24.04
- NetBox: `https://192.168.10.95`
- Versión de NetBox documentada: 4.4.2

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

El propietario verificó manualmente ambos servicios y scripts el 2026-07-24; desarrollo y producción terminaron activos y `/login` respondió HTTP 200. Esa evidencia corresponde a las ramas estables y no significa que un agente de IA tenga acceso al servidor.

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
- PR: `#3`, abierto como borrador hacia `develop`
- Versión de aplicación: `0.9.0`
- Objetivo: identidad multiusuario, roles, permisos, auditoría, perfil, protección de login, búsqueda global, estado del sistema y migraciones Alembic
- Estado: implementación amplia y pruebas automatizadas completadas fuera del servidor; pendiente de supervisión, respaldo y prueba manual en desarrollo
- No afirmar que esta rama está desplegada
- No quitar el estado de borrador, fusionar ni desplegar producción sin autorización explícita

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
- Alembic
- SQLite por defecto, configurable mediante `DATABASE_URL`
- Uvicorn
- HTML, CSS y JavaScript
- systemd
- Git y GitHub

Estructura relevante:

- `app/main.py`: aplicación, middleware, autenticación y rutas base.
- `app/core/config.py`: configuración.
- `app/core/security.py`: Argon2 y normalización segura de redirecciones.
- `app/core/auth.py`: sesión, permisos, CSRF y middleware.
- `app/core/database.py`: motor y sesiones SQLAlchemy.
- `app/core/migrations.py`: creación, adopción y actualización del esquema con Alembic.
- `app/models/access.py`: usuarios, roles, permisos y auditoría.
- `app/services/access_service.py`: reglas de identidad, autorización y protección de login.
- `app/services/netbox_client.py`: cliente REST principal de NetBox.
- `app/services/search_service.py`: búsqueda global concurrente.
- `app/services/system_service.py`: métricas no privilegiadas del servidor.
- `app/routers/admin.py`: administración de acceso y exportación de auditoría.
- `app/routers/profile.py`: perfil y contraseña propios.
- `app/routers/search.py`: búsqueda global y API JSON.
- `app/routers/system.py`: salud del sistema y API JSON.
- `app/routers/`: dispositivos, conexiones y racks.
- `app/templates/`: vistas Jinja2.
- `app/static/`: CSS, JavaScript e imágenes.
- `migrations/versions/`: revisiones Alembic.
- `tests/`: pruebas automatizadas.
- `.github/workflows/ci.yml`: integración continua.
- `scripts/`: despliegue controlado.
- `docs/`: documentación viva.
- `.env`: configuración sensible; nunca se versiona ni se imprime.

## Datos y límites

NetBox conserva dispositivos, interfaces, racks, cables, sitios y demás inventario técnico.

La base de NetDoc conserva únicamente:

- usuarios;
- roles;
- permisos;
- relaciones rol-permiso;
- eventos de auditoría;
- revisión Alembic aplicada.

Valor inicial:

`DATABASE_URL=sqlite:///./data/netdoc.db`

Cada entorno debe usar su propia base. `data/`, `*.db`, `*.sqlite` y `*.sqlite3` están ignorados.

## Migraciones Alembic

La revisión inicial es `20260724_0001` y crea las tablas `permissions`, `roles`, `role_permissions`, `users` y `audit_events`.

Durante el arranque, `ensure_database_schema()` aplica estas reglas:

1. Base vacía: ejecuta `alembic upgrade head`.
2. Base con `alembic_version`: actualiza hasta `head`.
3. Base heredada con todas las tablas esperadas: ejecuta `alembic stamp head` sin recrear tablas ni borrar datos.
4. Esquema parcial: detiene el arranque con un error explícito.

Antes del primer despliegue de esta rama debe respaldarse la base indicada por `DATABASE_URL`. El rollback de código no ejecuta `alembic downgrade` ni restaura automáticamente la base.

## Funcionalidades estables en `develop` y `main`

- Dashboard conectado a NetBox.
- Dispositivos con listado, búsqueda, filtros y paginación.
- Detalle de dispositivo e interfaces.
- Creación guiada de equipos.
- Consulta y creación de conexiones y cables.
- Listado y visualización 2D de racks.
- Inspector de equipos del rack.
- Integración REST con NetBox.
- Separación de desarrollo y producción.
- Scripts de despliegue con `flock`, validaciones, reintentos y rollback de código.

## Módulo implementado en la rama actual

- Autenticación multiusuario persistente.
- Bootstrap del primer administrador desde `ADMIN_USERNAME` y `ADMIN_PASSWORD_HASH`.
- Roles iniciales Administrador, Operador y Consulta.
- Roles personalizados.
- Once permisos por módulo.
- Creación, edición, activación, cambio de rol, contraseña y eliminación controlada de usuarios.
- Protección de la propia cuenta y del último administrador activo.
- Perfil de autoservicio para nombre, correo y contraseña propia.
- Verificación de contraseña actual antes del cambio.
- Navegación condicionada por permisos.
- Autorización en servidor para HTML y API.
- Recarga de identidad y permisos antes de cada solicitud protegida.
- Desactivación y cambios de rol efectivos en la siguiente solicitud.
- Pantalla 403.
- Protección temporal de login por usuario e IP.
- Límites configurables mediante `LOGIN_MAX_ATTEMPTS` y `LOGIN_WINDOW_SECONDS`.
- Respuesta HTTP 429 con `Retry-After` durante el bloqueo.
- Auditoría de login correcto, fallido y bloqueado, logout, perfil, usuarios, roles, exportaciones y solicitudes de creación de inventario.
- Filtros de auditoría por texto, acción, recurso, resultado y rango de fechas.
- Exportación CSV de hasta 10,000 eventos con neutralización de fórmulas.
- Búsqueda global de dispositivos, interfaces, racks, sitios y cables.
- Enlaces defensivos cuando NetBox no devuelve identificadores válidos.
- Módulo Sistema de solo lectura para CPU, RAM, disco, red, uptime, plataforma y proceso.
- API JSON para búsqueda y sistema.
- Esquema versionado con Alembic.
- Workflow de CI.

## Validaciones ejecutadas en la rama

Ejecutadas fuera del servidor:

- `python -m compileall -q app tests migrations`: correcto.
- `alembic heads`: una sola cabeza `20260724_0001`.
- Importación de `app.main`: correcta; 41 rutas.
- Carga sintáctica de 19 plantillas Jinja2: correcta.
- Sintaxis de ambos scripts de despliegue: correcta.
- 27 pruebas automatizadas: superadas.
- Inicialización SQLite en memoria y archivo temporal: correcta.
- Base vacía migrada hasta `head`: correcta.
- Adopción de base heredada completa: correcta.
- Actualización idempotente: correcta.
- Rechazo de esquema parcial: correcto.
- Creación de 11 permisos y tres roles: correcta.
- Creación y autenticación de usuarios de prueba: correcta.
- Persistencia de permisos personalizados: correcta.
- TestClient: login administrativo y páginas Usuarios, Roles y Auditoría: correctos.
- TestClient: denegación del rol Consulta: correcta.
- TestClient: login fallido y bloqueado visibles en Auditoría: correctos.
- TestClient: cinco fallos recientes producen HTTP 429 y `Retry-After`: correcto.
- TestClient: desactivación de cuenta invalida la sesión siguiente: correcto.
- TestClient: cambio de rol se aplica en la solicitud siguiente: correcto.
- TestClient: eliminación de otra cuenta y exportación CSV: correctas.
- TestClient: perfil, edición de datos y cambio de contraseña propia: correctos.
- TestClient: contraseña actual incorrecta impide el cambio: correcto.
- TestClient: Consulta usa Búsqueda y no puede abrir Sistema: correcto.
- Búsqueda agrupada con cliente NetBox simulado: correcta.
- Parsers de `/proc` y métricas del sistema: correctos.
- GitHub Actions valida dependencias, compilación, grafo Alembic, pruebas, importación, plantillas y scripts.

No se probaron todavía contra esta rama:

- systemd;
- puerto 8101;
- base persistente real del servidor;
- navegador completo;
- migración sobre la base real de desarrollo;
- integración real de búsqueda con NetBox 4.4.2;
- IP observada detrás de un posible proxy;
- producción o puerto 8100.

## Seguridad

- Nunca incluir tokens, contraseñas, hashes, claves ni `.env` en Git o respuestas.
- Las contraseñas se almacenan como hashes Argon2.
- Cuentas nuevas: mínimo 10 caracteres, mayúscula, minúscula y número.
- La seguridad real se aplica en servidor; ocultar menús no sustituye autorización.
- Operaciones administrativas y perfil usan CSRF.
- No registrar secretos en auditoría.
- Mantener al menos un administrador activo y prohibir autoeliminación.
- Reservar `system.view` al Administrador por defecto.
- El módulo Sistema no ejecuta comandos privilegiados.
- La exportación CSV neutraliza valores que parezcan fórmulas.
- Cada solicitud protegida consulta el estado actual del usuario y sus permisos.
- Un fallo de identidad se trata de forma cerrada y exige login.
- Desarrollo debe permanecer sin escritura NetBox.
- Rotar el token de NetBox previamente expuesto y reducir sus permisos.
- Respaldar la base antes de migraciones.
- No manipular manualmente `alembic_version` sin diagnóstico.
- Reevaluar SQLite y el rate limiting antes de múltiples workers o alta concurrencia.

## Despliegue

- `netdoc-deploy-dev`: actualiza solo `develop` y 8101.
- `netdoc-deploy-prod`: actualiza solo `main` y 8100; exige `DESPLEGAR` o `--yes`.

Los scripts se ejecutan como root para systemd, ejecutan Git, pip y Python como `sshtelenord`, validan entorno y propietarios, rechazan cambios locales, usan `flock`, instalan dependencias, compilan, importan, reinician solo su servicio, prueban `/login` con reintentos y restauran el commit anterior ante fallos.

El reinicio inicia Alembic automáticamente. El script no respalda ni restaura la base y no revierte migraciones. Antes del despliegue debe crearse un respaldo externo al flujo del script.

No desplegar la rama actual directamente. Primero revisar el PR #3, fusionar hacia `develop` solo con autorización y después ejecutar `netdoc-deploy-dev`.

## Trabajo pendiente inmediato

1. Confirmar el CI del último commit documental.
2. Revisar el diff completo del PR #3.
3. Confirmar el ADR 0005 y la migración `20260724_0001`.
4. Mantener el PR como borrador.
5. No fusionar sin autorización del propietario.
6. Tras aprobación, fusionar únicamente hacia `develop`.
7. Identificar `DATABASE_URL` de desarrollo sin exponer secretos.
8. Respaldar la base de desarrollo.
9. Desplegar solo en 8101.
10. Confirmar `alembic current` y `alembic heads`.
11. Probar login y navegación con Administrador, Operador y Consulta.
12. Probar perfil, usuarios, roles, contraseñas, desactivación, eliminación y denegaciones directas por URL.
13. Probar el bloqueo temporal de login con una cuenta de prueba.
14. Revisar filtros y exportación de Auditoría.
15. Probar Búsqueda con datos reales.
16. Revisar métricas de Sistema y confirmar que no realiza acciones.
17. Verificar permisos de la base, respaldo y `.env`.
18. Corregir incidencias antes de cualquier PR hacia `main`.

Después se planifican respaldo y recuperación automatizados, retención de auditoría, manejo diferenciado de fallos de base, rate limiting distribuido, edición controlada de inventario, patch panels, topologías, 3D, errores centralizados, métricas históricas y alertas.

## Validaciones obligatorias antes de terminar una tarea

- Revisar el diff completo.
- `python -m compileall -q app tests migrations`.
- `alembic heads`.
- `python -m unittest discover -s tests -v`.
- Importar `app.main`.
- Cargar plantillas Jinja2.
- Validar scripts modificados con `bash -n`.
- Revisar enlaces Markdown.
- Buscar secretos y claves privadas.
- Declarar qué no se pudo probar.
- Actualizar `CHANGELOG.md`, `PROJECT_STATUS.md`, documentación operativa y ADR aplicable.

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
12. `app/core/migrations.py`
13. `migrations/versions/20260724_0001_access_control.py`

## Información que nunca debe inventarse

- Secretos o contenido de `.env`.
- Acceso al servidor.
- Pruebas o despliegues no ejecutados.
- Estado de una base del servidor no inspeccionada.
- Funcionalidades no presentes en la rama.
- Resultado de una migración no ejecutada.
- Nombre o valor de la cookie de producción si no está documentado.
- Permisos o comportamiento de NetBox no verificados.

## Formato esperado de respuesta del agente

- Explicar primero el estado real y el riesgo principal.
- Separar claramente hechos verificados, inferencias y tareas pendientes.
- Entregar archivos completos cuando se modifique código.
- No ocultar errores ni afirmar éxito sin evidencia.
- No fusionar, desplegar o tocar producción salvo instrucción explícita.
- Para comandos del servidor, indicar exactamente dónde pegarlos y evitar exponer secretos.
- Mantener respuestas en español, directas y orientadas a la siguiente acción segura.