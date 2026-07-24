# Estado del proyecto: NetDoc

- **Propósito:** interfaz operativa para consultar, crear y visualizar inventario de red cuyo origen oficial es NetBox.
- **Estado general:** En progreso.
- **Última actualización:** 2026-07-24.
- **Versión documental:** 1.4.
- **Versión de aplicación de la rama:** 0.9.0.
- **Responsable / repositorio:** Luis Emilio García Pichardo / `tito9903-byte/netdoc`.
- **Ramas:** producción `main`; desarrollo `develop`; trabajo actual `feature/access-control-audit`.

## Resumen ejecutivo

La versión estable mantiene dashboard, inventario, conexiones, racks 2D y despliegue separado. El PR #3 incorpora identidad multiusuario, RBAC y auditoría, además de una segunda ola de funcionalidades: búsqueda global, salud del sistema, eliminación controlada de usuarios, filtros administrativos y exportación CSV. La rama requiere todavía supervisión y despliegue exclusivo en el puerto 8101 antes de fusionarse.

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
- SQLite es el valor inicial de `DATABASE_URL`; cada entorno debe tener su propia base.
- `PermissionMiddleware` recarga la identidad activa y los permisos antes de cada solicitud protegida.
- Las métricas de Sistema se obtienen mediante lecturas no privilegiadas de Python y `/proc`; no ejecutan comandos ni modifican servicios.

## Módulos

### Completado en `develop` y `main`

Dashboard, dispositivos e interfaces, filtros y paginación, creación guiada de equipos, conexiones y cables, racks 2D, integración NetBox, sesiones separadas y despliegue controlado.

### En progreso en `feature/access-control-audit`

- Autenticación multiusuario y contraseñas Argon2.
- Roles Administrador, Operador y Consulta, roles personalizados y 11 permisos.
- Creación, edición, activación, cambio de rol, contraseña y eliminación controlada de usuarios.
- Protección de la propia cuenta y del último administrador activo.
- Auditoría de accesos, fallos, cambios administrativos y operaciones guiadas.
- Filtros de auditoría por texto, acción, recurso, resultado y rango de fechas.
- Exportación CSV de hasta 10,000 eventos, con mitigación de fórmulas de hoja de cálculo.
- Búsqueda global simultánea de dispositivos, interfaces, racks, sitios y cables.
- Módulo Sistema: CPU, carga, RAM, disco, red, uptime, plataforma y proceso.
- API JSON para búsqueda y sistema.
- Navegación y rutas protegidas por permisos.

### Planificado

Migraciones Alembic, respaldo/retención de auditoría, bloqueo por intentos fallidos, recuperación ante fallo de base, edición/eliminación de inventario, desconexión de cables, patch panels, topologías, 3D, métricas históricas y alertas.

## Validaciones locales de la rama

Ejecutadas fuera del servidor:

- `python -m compileall -q app tests`: correcto.
- Importación de `app.main`: correcta; 38 rutas registradas.
- Análisis sintáctico de 18 plantillas Jinja2: correcto.
- Sintaxis de ambos scripts de despliegue: correcta.
- 17 pruebas automatizadas: superadas.
- Cobertura nueva: búsqueda agrupada, parsers de `/proc`, métricas del sistema, eliminación de usuario, exportación CSV, acceso a Sistema y permiso de Búsqueda.

Pendiente: confirmar GitHub Actions en el commit final, desplegar mediante systemd, validar la base persistente de desarrollo, probar con navegador y datos reales de NetBox, y revisar todos los roles en 8101.

## Riesgos y deuda

- El esquema inicial aún usa `create_all`; cambios posteriores deben usar Alembic.
- SQLite debe reevaluarse antes de varios workers o mayor concurrencia.
- El token de NetBox previamente expuesto debe rotarse y reducirse a mínimo privilegio.
- Las búsquedas dependen de los filtros `q` disponibles en NetBox y deben validarse con los datos reales.
- Las métricas actuales son instantáneas y acumuladas desde el arranque; no sustituyen una plataforma histórica de monitoreo.
- Falta definir retención, respaldo y eliminación segura de eventos de auditoría.

## Próximo objetivo

**En progreso:** mantener el PR #3 como borrador, confirmar CI, supervisar el diff y el ADR 0005, y después fusionar únicamente hacia `develop`. La prueba operativa se realizará solo en 8101 antes de considerar `main`.

## Reglas de mantenimiento

Actualizar este documento en todo PR que modifique funcionalidad, arquitectura, seguridad, despliegues, dependencias, pruebas, riesgos o prioridades. Estados permitidos: **Completado**, **En progreso**, **Planificado**, **Bloqueado**, **Diferido** y **Requiere verificación**.
