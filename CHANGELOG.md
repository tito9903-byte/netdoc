# Changelog

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las futuras versiones seguirán Semantic Versioning.

## Unreleased

### Added

- Dashboard conectado a NetBox.
- Consulta y detalle de dispositivos.
- Creación guiada de equipos.
- Conexiones entre interfaces.
- Visualización de racks en 2D.
- Inicio de sesión administrativo.
- Documentación inicial del proyecto.
- Índice documental, estado vivo, prompt de continuidad, glosario, pruebas y documentación operativa.
- Cuatro ADR sobre plataforma dedicada, separación de entornos, NetBox y documentación como código.
- Scripts independientes de despliegue para desarrollo y producción con comprobaciones y rollback.
- Bloqueo de despliegues simultáneos con `flock`.
- Verificación de `.env`, árbol Git limpio, propietarios y archivo de dependencias antes de actualizar.
- Comprobación HTTP con reintentos y aceptación de HTTP 200 o cualquier 3xx.

### Changed

- README y contribución alineados al flujo `feature/*` → `develop` → `main`.
- Arquitectura, roadmap e integración NetBox ampliados y enlazados.
- Git, pip y Python de los despliegues se ejecutan como `sshtelenord`; systemd y comprobaciones operativas permanecen bajo root.
- El rollback informa si alguno de sus pasos requiere revisión manual.
- El prompt maestro de continuidad ahora es autocontenido.

### Security

- Reglas explícitas para secretos, mínimo privilegio, separación de entornos y verificación previa.
- Protección contra despliegues con `.env` versionado o no ignorado.
- Rechazo de cambios locales, archivos no rastreados y propietarios inesperados antes de desplegar.