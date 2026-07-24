# Estado del proyecto: NetDoc

- **Propósito:** interfaz operativa para consultar, crear y visualizar inventario de red cuyo origen oficial es NetBox.
- **Estado general:** En progreso.
- **Última actualización:** 2026-07-24.
- **Versión documental:** 1.1.
- **Responsable / repositorio:** Luis Emilio García Pichardo / `tito9903-byte/netdoc`.
- **Ramas:** producción `main`; desarrollo `develop`; trabajo actual `feature/access-control-audit`.

## Resumen ejecutivo

La consulta y documentación de inventario, las operaciones guiadas y los racks 2D están operativos en desarrollo y producción. La rama actual incorpora una primera versión integral de usuarios, roles, permisos y auditoría, pero todavía requiere revisión del propietario, prueba manual en el puerto 8101 y promoción mediante PR antes de llegar a producción.

## Entornos y servicios

| Entorno | Estado conocido | Ruta | Rama | Servicio | Puerto | Sesión |
|---|---|---|---|---|---:|---|
| Producción | Verificado manualmente por el propietario | `/opt/netdoc-prod` | `main` | `netdoc-prod` | 8100 | independiente |
| Desarrollo | Verificado manualmente por el propietario | `/opt/netdoc-dev` | `develop` | `netdoc-dev` | 8101 | `netdoc_dev_session` |

Servidor dedicado: `192.168.10.93`; NetBox configurado: `https://192.168.10.95`. Desarrollo debe usar `NETBOX_WRITE_ENABLED=false`. El respaldo temporal `/opt/netbox-documental` no es producción activa y requiere decisión formal antes de eliminarse.

### Evidencia operativa conocida

El propietario verificó manualmente el 2026-07-24:

- Producción: servicio `netdoc-prod` activo y `/login` en el puerto 8100 respondió HTTP 200.
- Desarrollo: servicio `netdoc-dev` activo y `/login` en el puerto 8101 respondió HTTP 200.
- Los comandos `netdoc-deploy-prod` y `netdoc-deploy-dev` fueron ejecutados en el servidor y finalizaron con HTTP 200.

Estas verificaciones corresponden a la versión actualmente fusionada en `main` y `develop`; no validan todavía la rama `feature/access-control-audit`.

## Arquitectura, tecnologías e integración

FastAPI sirve HTML Jinja2 y estáticos; routers y servicios consumen REST de NetBox con HTTPX. Pydantic Settings carga configuración, SessionMiddleware mantiene sesiones y Argon2 protege contraseñas. El nuevo módulo usa SQLAlchemy para identidades, roles, permisos y eventos de auditoría; por defecto cada entorno crea su propia base SQLite en `data/netdoc.db`, configurable mediante `DATABASE_URL`. NetBox continúa siendo la fuente oficial del inventario técnico.

## Módulos

- **Completado en `develop`/`main`:** dashboard, consulta, búsqueda, filtros, paginación y detalle de dispositivos e interfaces; creación guiada de equipos; consulta y creación de cables; listado y elevación 2D de racks; integración REST con NetBox; sesiones separadas; despliegue controlado para ambos entornos.
- **En progreso en `feature/access-control-audit`:** cuentas persistentes, autenticación multiusuario, roles, permisos, navegación por privilegios, administración de usuarios, restablecimiento de contraseñas y auditoría.
- **Planificado:** edición/eliminación controlada de inventario, patch panels y puertos, edición/desconexión de cables, búsqueda global, topologías, 3D, manejo centralizado de errores, observabilidad, exportación de auditoría y migraciones formales de esquema.
- **Bloqueado:** ninguno registrado.
- **Diferido:** eliminación del respaldo temporal.

## Controles del módulo de acceso

- Roles iniciales: Administrador, Operador y Consulta.
- Nueve permisos separados por dashboard, dispositivos, conexiones, racks y administración.
- El administrador conserva acceso completo.
- No se permite desactivar la propia cuenta ni dejar el sistema sin un administrador activo.
- Los cambios de contraseña usan Argon2 y validación mínima de complejidad.
- Las sesiones almacenan identidad, rol y permisos; otros usuarios reciben cambios de rol al iniciar sesión nuevamente.
- La base de datos y su directorio están excluidos de Git.

## Pruebas y validaciones de la rama actual

Ejecutadas fuera del servidor sobre el código de la rama:

- Compilación de sintaxis de los módulos Python nuevos y modificados: correcta.
- Inicialización de una base SQLite temporal y creación de roles/permisos iniciales: correcta.
- Creación y autenticación de un usuario de prueba: correcta.
- Carga sintáctica de las nuevas plantillas Jinja2: correcta.
- `python -m unittest tests.test_access_control -v`: cuatro pruebas superadas.
- Comprobación aislada del middleware: una solicitud no autenticada a `/` fue redirigida a `/login`.

No se probaron todavía esta rama en systemd, el puerto 8101, una base persistente real ni la integración completa del navegador con NetBox.

## Deuda, problemas y riesgos

- La primera versión crea el esquema automáticamente; antes de cambios futuros de tablas debe adoptarse una migración formal con Alembic.
- SQLite es apropiado para la etapa y el proceso actual, pero debe reevaluarse si aumenta la concurrencia o se ejecutan varios workers.
- El token de NetBox expuesto anteriormente debe rotarse y limitarse al mínimo privilegio.
- Las sesiones abiertas antes de activar la nueva autenticación deberán iniciarse nuevamente.
- Falta prueba manual de todos los roles y flujos de administración en desarrollo.

## Decisiones y referencias

Los ADR aceptados cubren plataforma dedicada, separación de entornos, NetBox como fuente oficial y documentación como código. El [ADR 0005](adr/0005-local-identity-rbac-audit.md) propone la persistencia local para identidad y auditoría. Consulte también [arquitectura](ARCHITECTURE.md), [seguridad](SECURITY.md), [pruebas](TESTING.md) y [despliegue](DEPLOYMENT.md).

## Próximo objetivo

**En progreso:** completar revisión técnica del módulo de acceso, abrir PR hacia `develop`, desplegar solo en desarrollo, validar inicio de sesión, usuarios, roles, permisos y auditoría; corregir incidencias antes de promover a `main`.

## Reglas de mantenimiento del documento

Actualice este documento en todo PR que modifique funcionalidades, arquitectura, seguridad, despliegues, dependencias, módulos, estado de pruebas, riesgos, prioridades, problemas conocidos o decisiones técnicas. Use solo: **Completado**, **En progreso**, **Planificado**, **Bloqueado**, **Diferido** o **Requiere verificación**.
