# Estado del proyecto: NetDoc

- **Propósito:** interfaz operativa para consultar, crear y visualizar inventario de red cuyo origen oficial es NetBox.
- **Estado general:** En progreso.
- **Última actualización:** 2026-07-24.
- **Versión documental:** 1.2.
- **Responsable / repositorio:** Luis Emilio García Pichardo / `tito9903-byte/netdoc`.
- **Ramas:** producción `main`; desarrollo `develop`; trabajo actual `feature/access-control-audit`.

## Resumen ejecutivo

La consulta y documentación de inventario, las operaciones guiadas y los racks 2D están operativos en desarrollo y producción. La rama actual incorpora una primera versión integral de usuarios, roles, permisos y auditoría. El código y el workflow de CI pasan sus validaciones, pero todavía requiere supervisión del propietario y prueba manual en el puerto 8101 antes de fusionarse.

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
- Las personalizaciones de permisos de Operador y Consulta no son reemplazadas al reiniciar.
- Las sesiones almacenan identidad, rol y permisos; otros usuarios reciben cambios de rol al iniciar sesión nuevamente.
- La base de datos y su directorio están excluidos de Git.

## Pruebas y validaciones de la rama actual

Ejecutadas fuera del servidor:

- Compilación de los módulos Python nuevos y modificados: correcta.
- Inicialización de SQLite en memoria y archivo temporal: correcta.
- Creación de roles y permisos iniciales: correcta.
- Creación y autenticación de usuarios: correcta.
- Carga sintáctica de las nuevas plantillas Jinja2: correcta.
- Ocho pruebas automatizadas locales: superadas.
- TestClient: login administrativo, páginas de Usuarios/Roles/Auditoría, denegación del rol Consulta y auditoría de login fallido: correctos.
- GitHub Actions `NetDoc CI`: completado correctamente; instalación, compilación, pruebas, importación de `app.main`, plantillas y scripts finalizaron con éxito.

No se probaron todavía esta rama mediante systemd, el puerto 8101, la base persistente real del servidor ni el navegador con NetBox real.

## Deuda, problemas y riesgos

- La primera versión crea el esquema automáticamente; antes de cambios futuros de tablas debe adoptarse una migración formal con Alembic.
- SQLite es apropiado para la etapa y el proceso actual, pero debe reevaluarse si aumenta la concurrencia o se ejecutan varios workers.
- El token de NetBox expuesto anteriormente debe rotarse y limitarse al mínimo privilegio.
- Las sesiones abiertas antes de activar la nueva autenticación deberán iniciarse nuevamente.
- Falta prueba manual de todos los roles y flujos de administración en desarrollo.
- Falta definir revocación inmediata de sesiones, retención/exportación de auditoría y protección contra intentos repetidos de login.

## Decisiones y referencias

Los ADR aceptados cubren plataforma dedicada, separación de entornos, NetBox como fuente oficial y documentación como código. El [ADR 0005](adr/0005-local-identity-rbac-audit.md) propone la persistencia local para identidad y auditoría. Consulte también [arquitectura](ARCHITECTURE.md), [seguridad](SECURITY.md), [pruebas](TESTING.md) y [despliegue](DEPLOYMENT.md).

## Próximo objetivo

**En progreso:** supervisar el PR #3, revisar el ADR 0005 y, tras aprobación, fusionar únicamente hacia `develop`; luego desplegar en 8101 y validar inicio de sesión, usuarios, roles, permisos y auditoría antes de cualquier promoción a `main`.

## Reglas de mantenimiento del documento

Actualice este documento en todo PR que modifique funcionalidades, arquitectura, seguridad, despliegues, dependencias, módulos, estado de pruebas, riesgos, prioridades, problemas conocidos o decisiones técnicas. Use solo: **Completado**, **En progreso**, **Planificado**, **Bloqueado**, **Diferido** o **Requiere verificación**.
