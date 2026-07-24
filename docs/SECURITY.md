# Seguridad

## Controles actuales

- `.env`, tokens de NetBox, secretos de sesión y configuración sensible permanecen fuera de Git.
- Las contraseñas se almacenan únicamente como hashes Argon2.
- Las cuentas nuevas exigen al menos 10 caracteres, mayúscula, minúscula y número.
- SessionMiddleware usa cookie, duración y opción `Secure` configurables por entorno.
- Desarrollo mantiene `NETBOX_WRITE_ENABLED=false`.
- Las rutas HTML y API se autorizan con permisos del rol en el servidor.
- Antes de cada solicitud protegida se vuelve a consultar la cuenta y sus permisos en la base.
- Las acciones administrativas y operaciones guiadas usan tokens CSRF.
- La aplicación impide que un administrador desactive o elimine su propia cuenta, o deje el sistema sin un administrador activo.
- La base local se excluye de Git y cada entorno debe usar almacenamiento independiente.
- SQLite activa restricciones de claves foráneas.

## Identidades, roles y sesiones

Los roles iniciales son Administrador, Operador y Consulta. Debe aplicarse mínimo privilegio y crear roles personalizados cuando los perfiles iniciales resulten demasiado amplios. El administrador conserva todos los permisos. Las variables `ADMIN_USERNAME` y `ADMIN_PASSWORD_HASH` solo crean la primera cuenta cuando la base está vacía.

La cookie de sesión contiene identidad y datos de presentación, pero no es la autoridad final. En cada ruta protegida, NetDoc carga nuevamente el usuario activo, el rol y los permisos. Por ello, la desactivación de una cuenta y los cambios de rol o permisos se aplican en la siguiente solicitud sin esperar un nuevo inicio de sesión. Las sesiones antiguas que no contienen un identificador válido son enviadas al login.

Un fallo de lectura de identidad se trata de forma cerrada: la sesión se limpia y se exige autenticación. Queda pendiente distinguir en la interfaz un fallo de base de datos de una sesión realmente revocada.

## Auditoría

Se registran inicios de sesión correctos y fallidos, cierres de sesión, cambios de usuarios y roles, y solicitudes de creación de equipos o conexiones. Los eventos pueden incluir usuario, IP, agente del navegador, recurso, resultado y descripción. Nunca deben registrar contraseñas, hashes, token de NetBox, secreto de sesión ni contenido de `.env`.

La auditoría de aplicación no sustituye los logs de systemd, NetBox ni del sistema operativo. La exportación CSV requiere `audit.view`, se limita a 10,000 eventos y antepone una comilla a valores que comienzan con `=`, `+`, `-` o `@` para reducir el riesgo de fórmulas. Falta definir retención y revisión periódica.

## Búsqueda y métricas del sistema

La búsqueda global utiliza únicamente solicitudes GET a NetBox y enlaces internos. Los errores de un módulo se presentan sin degradar los demás y no se muestran tokens ni cabeceras de autorización.

El módulo Sistema requiere `system.view` y solo realiza lecturas no privilegiadas del sistema operativo. No ejecuta comandos, no reinicia servicios y no muestra `.env`, argumentos sensibles ni secretos. La plataforma y el ejecutable pueden revelar información operativa, por lo que este permiso se reserva al Administrador por defecto.

## Persistencia

`DATABASE_URL` permite seleccionar el motor. El valor inicial `sqlite:///./data/netdoc.db` es apropiado para el proceso único actual. El archivo debe pertenecer al usuario del servicio y tener permisos restrictivos. No debe copiarse entre desarrollo y producción. Antes de usar varios workers o una carga mayor debe evaluarse PostgreSQL.

El esquema inicial se crea automáticamente. Todo cambio posterior de tablas debe realizarse mediante migraciones versionadas y respaldos previos; no se debe editar manualmente una base de producción.

## Reglas operativas

Proteja `.env`, la base de datos, hashes, claves SSH/deploy keys y certificados con permisos restrictivos; no imprima su contenido. Ejecute servicios con permisos mínimos. Revise entradas, diffs, dependencias, pruebas y logs antes de promover. Los scripts no modifican ni eliminan `.env` ni la base de datos.

Antes de desplegar el módulo de acceso:

1. Respaldar cualquier base existente.
2. Confirmar que desarrollo y producción usan rutas independientes.
3. Verificar el administrador inicial sin exponer su hash.
4. Probar roles, denegaciones y revocación inmediata en desarrollo.
5. Confirmar que `data/` y los archivos de base están ignorados.
6. Verificar que el archivo de base pertenece a `sshtelenord` y no es legible por usuarios innecesarios.

## Secretos e incidentes

Rote tokens, secretos de sesión y credenciales de inmediato tras sospecha de exposición: revóquelos, sustitúyalos en el servidor, revise accesos y documente el incidente sin publicar el secreto. El token de NetBox expuesto previamente en capturas debe rotarse y reducirse al mínimo privilegio.

Riesgos pendientes: ausencia de MFA, falta de política de bloqueo por intentos fallidos, migraciones aún no versionadas, retención de auditoría sin definir, diferenciación de fallos de base, exposición operativa excesiva si se concede `system.view` sin criterio y pruebas de seguridad automatizadas todavía parciales.
