# Changelog

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y
las futuras versiones seguirán Semantic Versioning.

## Unreleased

### Added
- Índice documental, estado vivo, prompt de continuidad, glosario, pruebas y documentación operativa.
- Cuatro ADR sobre plataforma dedicada, entornos, NetBox y documentación como código.
- Scripts independientes de despliegue para desarrollo y producción con comprobaciones y rollback.
- Comprobación de árbol Git limpio y archivo de dependencias antes de actualizar.

### Changed
- README y contribución alineados al flujo `feature/*` → `develop` → `main`.
- Arquitectura, roadmap e integración NetBox ampliados y enlazados.

- El rollback ahora informa si alguno de sus pasos requiere revisión manual.

### Security
- Reglas explícitas para secretos, mínimo privilegio, separación de entornos y verificación previa.
