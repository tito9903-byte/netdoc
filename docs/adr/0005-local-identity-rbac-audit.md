# ADR 0005: Identidad, RBAC y auditoría local

- **Estado:** Propuesto
- **Fecha:** 2026-07-24

## Contexto

NetDoc necesita múltiples cuentas, roles, permisos y trazabilidad de acciones. NetBox continúa siendo la fuente oficial del inventario técnico, pero no debe usarse como almacén de las identidades internas de NetDoc ni de su auditoría de aplicación.

## Problema

La autenticación inicial depende de una única cuenta configurada en `.env`. Esto no permite asignar privilegios diferentes, desactivar cuentas individualmente, restablecer contraseñas ni atribuir acciones a una identidad persistente.

## Decisión

NetDoc mantendrá una base relacional propia únicamente para usuarios, roles, permisos, relaciones rol-permiso y eventos de auditoría.

Se utilizará SQLAlchemy como capa de persistencia. El valor predeterminado de `DATABASE_URL` será `sqlite:///./data/netdoc.db`, con una base separada para desarrollo y producción. La configuración permitirá adoptar PostgreSQL si aumentan concurrencia o disponibilidad requerida.

El primer arranque crea el esquema inicial y carga tres roles del sistema: Administrador, Operador y Consulta. Si no existe el usuario indicado por `ADMIN_USERNAME`, se crea con `ADMIN_PASSWORD_HASH`. Una vez creada, la cuenta se administra desde NetDoc; las variables sirven únicamente para el arranque inicial.

Las contraseñas se almacenan con Argon2. La cookie de sesión conserva el identificador del usuario y datos de presentación. Antes de cada solicitud protegida, el middleware consulta la identidad activa y los permisos actuales en la base. La desactivación de una cuenta, la eliminación de una identidad y los cambios de rol o permisos se aplican en la siguiente solicitud.

Las operaciones administrativas usan CSRF y generan eventos de auditoría sin secretos. El acceso falla de forma cerrada si no puede cargarse una identidad válida.

## Límites

- NetBox conserva dispositivos, interfaces, racks, cables y demás inventario.
- La base de NetDoc no duplicará inventario técnico.
- Desarrollo y producción no compartirán usuarios, sesiones ni auditoría.
- El archivo de base y sus respaldos no se versionarán.
- La creación automática del esquema cubre solo la primera entrega; las modificaciones posteriores requieren Alembic.

## Alternativas consideradas

### Mantener una sola cuenta en `.env`

Rechazada porque no permite mínimo privilegio ni atribución individual.

### Confiar únicamente en permisos guardados dentro de la cookie

Rechazada porque una desactivación o cambio de rol no se aplicaría hasta renovar la sesión.

### Usar usuarios de NetBox directamente

Diferida. Acoplaría NetDoc a permisos y disponibilidad de NetBox y no resolvería por sí solo la auditoría interna.

### Servicio externo de identidad desde el inicio

Diferido. Es una alternativa futura para SSO/MFA, pero añade complejidad operativa antes de validar el modelo de permisos.

### PostgreSQL obligatorio desde el inicio

Diferido. SQLite reduce complejidad para el proceso único actual; `DATABASE_URL` mantiene abierta la migración.

## Consecuencias positivas

- Identidad individual y trazabilidad.
- Roles y permisos explícitos.
- Revocación y cambios de permisos efectivos en la siguiente solicitud.
- Administración independiente del inventario de NetBox.
- Separación entre desarrollo y producción.
- Posibilidad de migrar a otro motor relacional.

## Consecuencias negativas

- NetDoc incorpora estado persistente que debe respaldarse.
- Cada solicitud protegida realiza una lectura de identidad y permisos.
- Se requiere estrategia de migraciones y recuperación.
- SQLite debe reevaluarse antes de usar múltiples workers o alta concurrencia.
- Un fallo de base actualmente puede presentarse al usuario como una sesión invalidada.

## Riesgos

- Pérdida o corrupción de la base local.
- Permisos demasiado amplios.
- Registro accidental de información sensible.
- Bloqueo administrativo por cambios incorrectos.
- Diferencias de esquema entre entornos.
- Carga adicional por consultar permisos en cada solicitud.

## Medidas de mitigación

- Excluir `data/` y archivos de base de Git.
- Respaldar antes de despliegues y migraciones.
- Conservar al menos un administrador activo.
- Impedir que un administrador desactive su propia cuenta.
- No registrar contraseñas, hashes, tokens ni `.env`.
- Probar todos los roles, cambios y revocaciones en desarrollo.
- Incorporar Alembic antes del primer cambio de esquema posterior.
- Evaluar caché con invalidación explícita solo si las métricas muestran necesidad.

## Referencias internas

- [Estado del proyecto](../PROJECT_STATUS.md)
- [Arquitectura](../ARCHITECTURE.md)
- [Seguridad](../SECURITY.md)
- [Pruebas](../TESTING.md)
- [ADR 0003: NetBox como fuente oficial](0003-netbox-as-source-of-truth.md)
