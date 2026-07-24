# Arquitectura

## Propósito, alcance y límites

NetDoc ofrece una experiencia web para lectura y operaciones guiadas sobre el inventario de NetBox. NetBox conserva la autoridad sobre dispositivos, interfaces, racks y cables. NetDoc mantiene únicamente datos propios de la aplicación: usuarios, roles, permisos, sesiones y auditoría.

```mermaid
flowchart LR
  U[Navegador] --> N[NetDoc: FastAPI]
  N --> B[API REST de NetBox]
  B --> I[Inventario técnico oficial]
  N --> D[(Base local NetDoc)]
  D --> A[Usuarios, roles, permisos y auditoría]
```

```mermaid
flowchart TB
  M[app/main.py] --> C[app/core]
  M --> R[app/routers]
  R --> S[app/services]
  R --> T[templates y static]
  S --> B[NetBox REST]
  C --> DB[SQLAlchemy]
  DB --> L[(SQLite por defecto)]
  DPL[scripts] --> SYS[systemd]
```

## Organización y flujos

- `app/main.py`: crea FastAPI, configura middleware, autenticación y rutas principales.
- `app/core/config.py`: carga configuración desde `.env`.
- `app/core/database.py`: motor SQLAlchemy, sesiones transaccionales e inicialización del esquema.
- `app/core/auth.py`: identidad de sesión, CSRF común y autorización por permisos.
- `app/core/security.py`: hash y verificación Argon2.
- `app/models/access.py`: entidades de usuario, rol, permiso y evento de auditoría.
- `app/services/access_service.py`: reglas de negocio del control de acceso.
- `app/routers/admin.py`: pantallas y acciones administrativas.
- `app/services/netbox_client.py` y servicios especializados: integración con NetBox.
- `app/services/search_service.py`: búsqueda concurrente y normalización de resultados de varios módulos.
- `app/services/system_service.py`: métricas no privilegiadas del host y del proceso.
- `app/routers/search.py` y `app/routers/system.py`: vistas y API JSON de búsqueda y salud.
- `app/templates` y `app/static`: presentación.
- `scripts`: despliegue operativo, sin lógica de negocio.

## Autenticación y autorización

En el arranque, NetDoc crea las tablas ausentes y carga permisos y roles iniciales. Si no existe una cuenta con `ADMIN_USERNAME`, se crea usando `ADMIN_PASSWORD_HASH`; estas variables son un mecanismo de arranque, no un reemplazo de la gestión de usuarios.

Tras validar la contraseña Argon2, la sesión almacena el identificador del usuario y una copia de presentación de su rol y permisos. Antes de atender cada ruta protegida, `PermissionMiddleware` vuelve a consultar la identidad activa en la base y actualiza esos datos de sesión. Como resultado:

- una cuenta desactivada pierde acceso en la siguiente solicitud;
- un cambio de rol o permisos se aplica en la siguiente solicitud;
- una cuenta eliminada debe autenticarse nuevamente;
- un fallo al cargar identidad se trata de forma cerrada y devuelve al login.

Las rutas administrativas realizan además verificaciones explícitas y CSRF. La navegación oculta opciones que el rol no puede usar, pero la seguridad real permanece en el servidor.

Roles iniciales:

- **Administrador:** todos los permisos y gestión completa.
- **Operador:** consulta y operaciones guiadas de dispositivos y conexiones.
- **Consulta:** acceso de solo lectura a dashboard, búsqueda global, dispositivos, conexiones y racks.

## Persistencia

`DATABASE_URL` selecciona la base de datos. El valor predeterminado es `sqlite:///./data/netdoc.db`; desarrollo y producción deben conservar bases independientes. El archivo local y el directorio `data/` no se versionan. SQLAlchemy permite migrar más adelante a PostgreSQL sin cambiar el modelo de dominio.

La primera entrega usa `Base.metadata.create_all()` para establecer el esquema inicial. Esta decisión solo cubre el primer despliegue; cualquier evolución posterior de tablas requiere migraciones versionadas con Alembic.

SQLite habilita claves foráneas. El diseño actual supone un único proceso Uvicorn por entorno; antes de múltiples workers o mayor concurrencia debe reevaluarse el motor.

## Auditoría

Los eventos registran fecha, usuario, acción, recurso, identificador, resultado, descripción, IP y agente del navegador. Se registran accesos correctos y fallidos, cierre de sesión, administración de usuarios y roles, eliminación de cuentas, exportaciones y solicitudes de creación de dispositivos o conexiones. La vista permite filtrar por acción, recurso, resultado y fechas. La exportación CSV se limita a 10,000 filas y neutraliza celdas que podrían convertirse en fórmulas. Nunca deben incluirse contraseñas, hashes, tokens ni contenido de `.env`.

## Búsqueda global

`search_service` consulta en paralelo dispositivos, interfaces, racks, sitios y cables mediante el filtro `q` de NetBox. Cada sección falla de forma independiente, por lo que un endpoint no disponible no impide mostrar los demás resultados. Los enlaces conducen a vistas internas de NetDoc y la operación es siempre de solo lectura.

## Estado del sistema

`system_service` usa `os`, `shutil`, `platform`, `socket` y lecturas de `/proc` para presentar CPU, carga, memoria, disco, red y uptime. No invoca shell, `systemctl`, sudo ni comandos privilegiados. Las métricas son instantáneas o acumuladas desde el arranque y no sustituyen monitoreo histórico.

## Integración con NetBox

El navegador solicita una ruta, FastAPI valida identidad y permiso, el router usa un servicio y este consulta NetBox; la respuesta se presenta en Jinja2. La creación guiada de equipos y cables requiere autenticación, permiso, CSRF y `NETBOX_WRITE_ENABLED=true`. NetBox conserva las validaciones finales y el historial técnico.

## Dependencias y operación

Dependencias principales: Python, FastAPI, Jinja2, HTTPX, Pydantic Settings, SessionMiddleware, Argon2, SQLAlchemy y Uvicorn. La disponibilidad depende de FastAPI, systemd, la base de identidad y NetBox.

## Limitaciones y trabajo futuro

- Falta prueba integral del módulo en el servidor de desarrollo.
- Falta retención configurable y respaldo automatizado de auditoría.
- El fallo de base actualmente invalida la sesión en lugar de mostrar una página operativa diferenciada.
- Antes de cambiar el esquema debe incorporarse Alembic.
- Continúan planificados edición controlada de inventario, patch panels, topologías, 3D, métricas históricas y alertas.
