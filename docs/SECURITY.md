# Seguridad

## Controles actuales

Se aplica mínimo privilegio: `.env` está ignorado, tokens/configuración de
NetBox y secreto de sesión se cargan fuera de Git; la contraseña administrativa
se verifica mediante hash Argon2. Los entornos usan `.env`, sesiones, servicios
y puertos independientes; desarrollo restringe escritura con
`NETBOX_WRITE_ENABLED=false`. La aplicación aplica autenticación y comprobación
CSRF en operaciones guiadas identificadas.

## Reglas operativas

Proteja `.env`, hashes, claves SSH/deploy keys y certificados con permisos
restrictivos; no imprima su contenido. Ejecute servicios con permisos mínimos.
Revise entradas, diffs, dependencias y logs antes de promover. Los scripts no
modifican ni eliminan `.env`. Registre acciones operativas conforme a las
capacidades existentes; la auditoría interna es Planificado.

## Secretos e incidentes

Rote tokens, secretos de sesión y credenciales según política operativa y de
inmediato tras sospecha de exposición: revóquelos, sustitúyalos en servidor,
revise accesos y documente el incidente sin publicar el secreto. Antes de
desplegar: revisar rama/commit, permisos, `.env` existente, dependencias y
pruebas; después: servicio, HTTP y logs. Riesgos conocidos: tokens demasiado
amplios, ausencia de auditoría interna y pruebas de seguridad automatizadas.
