# ADR 0005: Identidad, RBAC y auditoría local

- **Estado:** Propuesto
- **Fecha:** 2026-07-24

## Contexto

NetDoc necesita múltiples cuentas, roles, permisos y trazabilidad de acciones. NetBox continúa siendo la fuente oficial del inventario técnico, pero no debe usarse como almacén de las identidades internas de NetDoc ni de su auditoría de aplicación.

## Problema

La autenticación inicial depende de una única cuenta configurada en `.env`. Esto no permite asignar privilegios diferentes, desactivar cuentas individualmente, restablecer contraseñas ni atribuir acciones a una identidad persistente.

## Decisión

NetDoc mantendrá una base relacional propia únicamente para:

- usuarios;
- roles;
- permisos;
- relaciones entre roles y permisos;
- eventos de auditoría.

Se utilizará SQLAlchemy como capa de persistencia. El valor predeterminado de `DATABASE_URL` será `sqlite:///./data/netdoc.db`, con una base separada para desarrollo y producción. La configuración permitirá adoptar PostgreSQL si aumentan concurrencia o disponibilidad requerida.

El primer arranque crea el esquema inicial y carga tres roles del sistema: Administrador, Operador y Consulta. Si no existe el usuario indicado por `ADMIN_USERNAME`, se crea con `ADMIN_PASSWORD_HASH`. Una vez creada, la cuenta se administra desde NetDoc; las variables sirven únicamente para el arranque inicial.

Las contraseñas se almacenan con Argon2. La sesión contiene identidad, rol y permisos. Un middleware aplica autorización en servidor y la interfaz oculta opciones no disponibles. Las operaciones administrativas usan CSRF y generan eventos de auditoría sin secretos.

## Límites

- NetBox conserva dispositivos, interfaces, racks, cables y demás inventario.
- La base de NetDoc no duplicará inventario técnico.
- Desarrollo y producción no compartirán usuarios, sesiones ni auditoría.
- El archivo de base y sus respaldos no se versionarán.
- La creación automática del esquema cubre solo la primera entrega; las modificaciones posteriores requieren Alembic.

## Alternativas consideradas

### Mantener una sola cuenta en `.env`

Rechazada porque no permite mínimo privilegio ni atribución individual.

### Usar usuarios de NetBox directamente

Diferida. Acoplaría NetDoc a permisos y disponibilidad de NetBox y no resolvería por sí solo la auditoría interna.

### Servicio externo de identidad desde el inicio

Diferido. Es una alternativa futura para SSO/MFA, pero añade complejidad operativa antes de validar el modelo de permisos.

### PostgreSQL obligatorio desde el inicio

Diferido. SQLite reduce complejidad para el proceso único actual; `DATABASE_URL` mantiene abierta la migración.

## Consecuencias positivas

- Identidad individual y trazabilidad.
- Roles y permisos explícitos.
- Administración independiente del inventario de NetBox.
- Separación entre desarrollo y producción.
- Posibilidad de migrar a otro motor relacional.

## Consecuencias negativas

- NetDoc incorpora estado persistente que debe respaldarse.
- Se requiere estrategia de migraciones y recuperación.
- Las sesiones abiertas pueden conservar permisos hasta un nuevo inicio de sesión.
- SQLite debe reevaluarse antes de usar múltiples workers o alta concurrencia.

## Riesgos

- Pérdida o corrupción de la base local.
- Permisos demasiado amplios.
- Registro accidental de información sensible.
- Bloqueo administrativo por cambios incorrectos.
- Diferencias de esquema entre entornos.

## Medidas de mitigación

- Excluir `data/` y archivos de base de Git.
- Respaldar antes de despliegues y migraciones.
- Conservar al menos un administrador activo.
- Impedir que un administrador desactive su propia cuenta.
- No registrar contraseñas, hashes, tokens ni `.env`.
- Probar todos los roles en desarrollo.
- Incorporar Alembic antes del primer cambio de esquema posterior.

## Referencias internas

- [Estado del proyecto](../PROJECT_STATUS.md)
- [Arquitectura](../ARCHITECTURE.md)
- [Seguridad](../SECURITY.md)
- [Pruebas](../TESTING.md)
- [ADR 0003: NetBox como fuente oficial](0003-netbox-as-source-of-truth.md)
