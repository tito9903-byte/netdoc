# Seguridad

## Controles actuales

- `.env`, tokens de NetBox, secretos de sesión y configuración sensible permanecen fuera de Git.
- Las contraseñas se almacenan únicamente como hashes Argon2.
- Las cuentas nuevas exigen al menos 10 caracteres, mayúscula, minúscula y número.
- SessionMiddleware usa cookie, duración y opción `Secure` configurables por entorno.
- Desarrollo mantiene `NETBOX_WRITE_ENABLED=false`.
- Las rutas HTML y API se autorizan con permisos del rol en el servidor.
- Las acciones administrativas y operaciones guiadas usan tokens CSRF.
- La aplicación impide que un administrador desactive su propia cuenta o elimine el último administrador activo.
- La base local se excluye de Git y cada entorno debe usar almacenamiento independiente.
- SQLite activa restricciones de claves foráneas.

## Identidades, roles y sesiones

Los roles iniciales son Administrador, Operador y Consulta. Debe aplicarse mínimo privilegio y crear roles personalizados cuando los perfiles iniciales resulten demasiado amplios. El administrador conserva todos los permisos. Las variables `ADMIN_USERNAME` y `ADMIN_PASSWORD_HASH` solo crean la primera cuenta cuando la base está vacía.

La sesión contiene ID de usuario, nombre, rol y permisos. Al modificar el rol de otro usuario, sus sesiones existentes pueden conservar permisos anteriores hasta que vuelva a iniciar sesión; para revocación urgente se debe desactivar la cuenta y reiniciar o invalidar sesiones mediante el procedimiento operativo que se defina.

## Auditoría

Se registran inicios de sesión correctos y fallidos, cierres de sesión, cambios de usuarios y roles, y solicitudes de creación de equipos o conexiones. Los eventos pueden incluir usuario, IP, agente del navegador, recurso, resultado y descripción. Nunca deben registrar contraseñas, hashes, token de NetBox, secreto de sesión ni contenido de `.env`.

La auditoría de aplicación no sustituye los logs de systemd, NetBox ni del sistema operativo. Falta definir retención, exportación protegida y revisión periódica.

## Persistencia

`DATABASE_URL` permite seleccionar el motor. El valor inicial `sqlite:///./data/netdoc.db` es apropiado para el proceso único actual. El archivo debe pertenecer al usuario del servicio y tener permisos restrictivos. No debe copiarse entre desarrollo y producción. Antes de usar varios workers o una carga mayor debe evaluarse PostgreSQL.

El esquema inicial se crea automáticamente. Todo cambio posterior de tablas debe realizarse mediante migraciones versionadas y respaldos previos; no se debe editar manualmente una base de producción.

## Reglas operativas

Proteja `.env`, la base de datos, hashes, claves SSH/deploy keys y certificados con permisos restrictivos; no imprima su contenido. Ejecute servicios con permisos mínimos. Revise entradas, diffs, dependencias, pruebas y logs antes de promover. Los scripts no modifican ni eliminan `.env` ni la base de datos.

Antes de desplegar el módulo de acceso:

1. Respaldar cualquier base existente.
2. Confirmar que desarrollo y producción usan rutas independientes.
3. Verificar el administrador inicial sin exponer su hash.
4. Probar roles y denegaciones en desarrollo.
5. Confirmar que `data/` y los archivos de base están ignorados.

## Secretos e incidentes

Rote tokens, secretos de sesión y credenciales de inmediato tras sospecha de exposición: revóquelos, sustitúyalos en el servidor, revise accesos y documente el incidente sin publicar el secreto. El token de NetBox expuesto previamente en capturas debe rotarse y reducirse al mínimo privilegio.

Riesgos pendientes: revocación inmediata de sesiones, ausencia de MFA, falta de política de bloqueo por intentos fallidos, migraciones aún no versionadas, retención de auditoría sin definir y pruebas de seguridad automatizadas limitadas.
