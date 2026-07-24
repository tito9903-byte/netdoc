# Contribuir a NetDoc

## Flujo

Parta de `develop`, cree `feature/<tema>`, haga cambios pequeños y abra un pull
request hacia `develop`. Tras revisión y pruebas en desarrollo se puede promover
un PR hacia `main`; no se programa directamente en `main`, no se fusiona
automáticamente y no se modifica `/opt/netdoc-prod` manualmente.

## Calidad y documentación

Use Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`,
`chore:`, `ci:`, `build:`, `perf:` y `revert:`. Actualice `CHANGELOG.md` y
`docs/PROJECT_STATUS.md` cuando cambien funcionalidades, arquitectura,
seguridad, despliegues, dependencias, pruebas, riesgos o prioridades. Cree o
reemplace un ADR para decisiones arquitectónicas. Consulte el [índice](docs/README.md).

Antes del PR ejecute las pruebas disponibles, compilación/importación y las
validaciones de scripts afectadas. Revise el diff, enlaces y secretos. La
Definición de Terminado exige revisión, documentación coherente, compatibilidad
con producción y resultados reales de validación. Nunca añada `.env`, tokens,
contraseñas, hashes, claves ni certificados.
