# Estado del proyecto: NetDoc

- **Propósito:** interfaz operativa para consultar, crear y visualizar inventario de red cuyo origen oficial es NetBox.
- **Estado general:** En progreso.
- **Última actualización:** 2026-07-24.
- **Versión documental:** 1.7.
- **Versión de aplicación de la rama:** 0.9.0.
- **Responsable / repositorio:** Luis Emilio García Pichardo / `tito9903-byte/netdoc`.
- **Ramas:** producción `main`; desarrollo `develop`; trabajo actual `feature/access-control-audit`.

## Resumen ejecutivo

La versión estable mantiene dashboard, inventario, conexiones, racks 2D y despliegue separado. El PR #3 incorpora identidad multiusuario, RBAC y auditoría, búsqueda global, salud del sistema, administración ampliada, perfil de autoservicio, protección temporal contra intentos repetidos de login y una base versionada mediante Alembic. La rama requiere todavía supervisión y despliegue exclusivo en el puerto 8101 antes de fusionarse.

## Entornos y servicios

| Entorno | Estado conocido | Ruta | Rama | Servicio | Puerto | Sesión |
|---|---|---|---|---|---:|---|
| Producción | Verificado manualmente por el propietario | `/opt/netdoc-prod` | `main` | `netdoc-prod` | 8100 | independiente |
| Desarrollo | Verificado manualmente por el propietario | `/opt/netdoc-dev` | `develop` | `netdoc-dev` | 8101 | `netdoc_dev_session` |

Servidor dedicado: `192.168.10.93`; NetBox: `https://192.168.10.95`. Desarrollo debe usar `NETBOX_WRITE_ENABLED=false`. El respaldo `/opt/netbox-documental` continúa diferido y no es producción activa.

El propietario verificó el 2026-07-24 ambos servicios con HTTP 200 y ejecutó correctamente `netdoc-deploy-dev` y `netdoc-deploy-prod`. Esa evidencia corresponde a las ramas estables y no valida todavía el PR #3.

## Arquitectura actual de la rama

- FastAPI, Jinja2, HTTPX, Pydantic Settings, SessionMiddleware y Uvicorn.
- NetBox conserva dispositivos, interfaces, racks, sitios, cables y demás inventario.
- SQLAlchemy conserva únicamente usuarios, roles, permisos y auditoría de NetDoc.
- Alembic mantiene el historial versionado del esquema local.
- SQLite es el valor inicial de `DATABASE_URL`; cada entorno debe tener su propia base.
- `PermissionMiddleware` recarga la identidad activa y los permisos antes de cada solicitud protegida.
- Las métricas de Sistema se obtienen mediante lecturas no privilegiadas de Python y `/proc`; no ejecutan comandos ni modifican servicios.
- Los intentos fallidos de login se consultan en Auditoría por usuario e IP dentro de una ventana configurable.

## Inicialización y migraciones

La revisión inicial `20260724_0001` crea permisos, roles, asociaciones, usuarios y auditoría. Al arrancar:

- una base vacía se migra hasta `head`;
- una base completa creada por la versión anterior con `create_all` se marca en `head` sin recrear tablas ni borrar datos;
- una base que ya contiene `alembic_version` se actualiza hasta `head`;
- un esquema parcial se rechaza para evitar ocultar corrupción o una instalación incompleta.

Antes del primer despliegue de esta rama debe respaldarse el archivo indicado por `DATABASE_URL`. Los scripts de despliegue no restauran automáticamente la base de datos.

## Módulos

### Completado en `develop` y `main`

Dashboard, dispositivos e interfaces, filtros y paginación, creación guiada de equipos, conexiones y cables, racks 2D, integración NetBox, sesiones separadas y despliegue controlado.

### En progreso en `feature/access-control-audit`

- Autenticación multiusuario y contraseñas Argon2.
- Roles Administrador, Operador y Consulta, roles personalizados y 11 permisos.
- Creación, edición, activación, cambio de rol, contraseña y eliminación controlada de usuarios.
- Perfil de autoservicio para actualizar nombre, correo y contraseña propia.
- Verificación de la contraseña actual antes del cambio y auditoría sin registrar secretos.
- Protección de la propia cuenta y del último administrador activo.
- Bloqueo temporal tras fallos repetidos del mismo usuario desde la misma IP, con respuesta HTTP 429 y `Retry-After`.
- Auditoría de accesos, fallos, bloqueos, cambios administrativos y operaciones guiadas.
- Filtros de auditoría por texto, acción, recurso, resultado y rango de fechas.
- Exportación CSV de hasta 10,000 eventos, con mitigación de fórmulas de hoja de cálculo.
- Búsqueda global simultánea de dispositivos, interfaces, racks, sitios y cables.
- Módulo Sistema: CPU, carga, RAM, disco, red, uptime, plataforma y proceso.
- API JSON para búsqueda y sistema.
- Navegación y rutas protegidas por permisos.
- Migración inicial Alembic y adopción controlada de bases heredadas completas.

### Planificado

Respaldo y retención automatizados de auditoría, recuperación operativa ante fallo de base, edición/eliminación de inventario, desconexión de cables, patch panels, topologías, 3D, métricas históricas, alertas y controles distribuidos de rate limiting para escenarios con varios workers.

## Validaciones de la rama

Ejecutadas fuera del servidor:

- `python -m compileall -q app tests migrations`: correcto.
- `alembic heads`: correcto; una sola cabeza `20260724_0001`.
- Importación de `app.main`: correcta; 41 rutas registradas.
- Análisis sintáctico de 19 plantillas Jinja2: correcto.
- Sintaxis de ambos scripts de despliegue: correcta.
- 27 pruebas automatizadas: superadas.
- Cobertura de migraciones: base vacía, adopción de esquema heredado completo, actualización idempotente y rechazo de esquema parcial.
- Cobertura funcional: búsqueda agrupada, parsers de `/proc`, métricas del sistema, eliminación de usuario, exportación CSV, Sistema, Búsqueda, perfil y bloqueo temporal de login.
- GitHub Actions `NetDoc CI`: compilación, grafo de migraciones, pruebas, importación, plantillas y scripts completados correctamente.

Pendiente: desplegar mediante systemd, respaldar y validar la base persistente de desarrollo, probar con navegador y datos reales de NetBox, y revisar todos los roles en 8101.

## Riesgos y deuda

- SQLite debe reevaluarse antes de varios workers o mayor concurrencia.
- El rollback del código no revierte automáticamente cambios de esquema ni restaura el archivo de base.
- El bloqueo actual usa Auditoría y alcance usuario/IP; para despliegues distribuidos debe validarse una estrategia centralizada.
- El token de NetBox previamente expuesto debe rotarse y reducirse a mínimo privilegio.
- Las búsquedas dependen de los filtros `q` disponibles en NetBox y deben validarse con los datos reales.
- Las métricas actuales son instantáneas y acumuladas desde el arranque; no sustituyen una plataforma histórica de monitoreo.
- Falta definir retención, respaldo y eliminación segura de eventos de auditoría.

## Próximo objetivo

**En progreso:** mantener el PR #3 como borrador, supervisar el diff y el ADR 0005, y después fusionar únicamente hacia `develop`. La prueba operativa se realizará solo en 8101 y comenzará con un respaldo de la base antes de considerar `main`.

## Reglas de mantenimiento

Actualizar este documento en todo PR que modifique funcionalidad, arquitectura, seguridad, despliegues, dependencias, pruebas, riesgos o prioridades. Estados permitidos: **Completado**, **En progreso**, **Planificado**, **Bloqueado**, **Diferido** y **Requiere verificación**.
