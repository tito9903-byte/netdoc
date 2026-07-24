# Prompt maestro de continuidad

> Estás continuando el desarrollo de NetDoc. Antes de modificar código, lee
> completamente `AGENTS.md`, `docs/PROJECT_STATUS.md`,
> `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/DEPLOYMENT.md`,
> `docs/OPERATIONS.md`, `CONTRIBUTING.md` y los ADR vigentes.

NetDoc es una plataforma web para operación y documentación de infraestructura;
NetBox es el inventario oficial. El alcance es interfaz FastAPI/Jinja2, servicios
HTTPX y operaciones guiadas; fuera de alcance están usuarios, roles, permisos y
auditoría internos hasta su próximo módulo. El servidor es dedicado: desarrollo
(`/opt/netdoc-dev`, `develop`, `netdoc-dev`, 8101) y producción
(`/opt/netdoc-prod`, `main`, `netdoc-prod`, 8100) son independientes. NetBox se
consume por REST mediante `.env`; desarrollo debe tener escritura deshabilitada.

Estado actual: autenticación administrativa, dashboard, dispositivos,
interfaces, creación guiada, conexiones/cables y racks 2D existen en código;
planificado: usuarios, roles, permisos, auditoría, patch panels, topologías,
3D, pruebas, seguridad y observabilidad. El próximo objetivo es usuarios,
roles, permisos y auditoría. `PROJECT_STATUS.md` es estado oficial, ADR son
decisiones oficiales, `ROADMAP.md` trabajo futuro y este prompt debe actualizarse
ante cambios estructurales.

Trabaja desde `develop` en `feature/*`, abre PR hacia `develop`, prueba en
desarrollo antes de promover a `main`. No modifiques producción directamente ni
fusionas PR automáticamente. Los despliegues están documentados: push no
despliega; los scripts actualizan solo su entorno. Usa PEP 8, responsabilidades
separadas, Conventional Commits y Markdown con enlaces relativos. Mantén
`PROJECT_STATUS.md`, `CHANGELOG.md` y ADR aplicable. Valida diff, compilación,
importación, scripts, enlaces, secretos y pruebas existentes.

## Información que nunca debe inventarse

Tokens, contraseñas, hashes, claves, IP no documentadas, servicios, permisos,
esquemas NetBox, resultados de pruebas, funcionalidades no implementadas,
acceso al servidor o externos, resultados de despliegue, versiones no
verificadas ni relaciones con proyectos no documentados. Nunca incluya secretos.

## Formato esperado de respuesta del agente

Indica qué entendiste, archivos revisados y a modificar, decisiones, validaciones
y resultados, limitaciones, qué debe probar el usuario, documentación actualizada
y pendientes. Una tarea termina con cambios revisados, documentación coherente,
validaciones reales, commit y PR sin fusión.
