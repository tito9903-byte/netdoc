# Instrucciones para agentes

Antes de cambiar archivos, lea `docs/PROJECT_STATUS.md`, `docs/ARCHITECTURE.md`,
`docs/SECURITY.md`, `docs/DEPLOYMENT.md`, `docs/OPERATIONS.md`,
`CONTRIBUTING.md` y los ADR vigentes. El código versionado es la fuente del
comportamiento; los ADR son la fuente de decisiones; `PROJECT_STATUS.md` es la
fuente de estado y prioridades.

- Cree `feature/*` desde `develop`; nunca programe en `main` ni modifique
  producción directamente. Entregue por pull request hacia `develop` y no lo
  fusione automáticamente.
- No incluya ni imprima secretos, `.env`, tokens, contraseñas, hashes, claves o
  certificados. No invente pruebas, despliegues, acceso a servidores ni
  integraciones. No mencione sistemas no documentados.
- NetBox es la fuente oficial del inventario. Mantenga responsabilidades entre
  configuración, seguridad, routers, servicios, plantillas, estáticos, scripts
  y documentación.
- Actualice `PROJECT_STATUS.md`, `CHANGELOG.md` y, si cambia una decisión de
  arquitectura, un ADR. Mantenga enlaces relativos y documentación en español.
- Ejecute las validaciones aplicables antes de terminar, comunique límites con
  honestidad y no altere el otro entorno desde scripts de despliegue.
