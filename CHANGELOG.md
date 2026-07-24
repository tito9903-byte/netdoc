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
- Persistencia local configurable con SQLAlchemy para identidades, roles, permisos y auditoría.
- Gestión de usuarios: creación, edición, activación, asignación de rol y restablecimiento de contraseña.
- Gestión de roles y permisos con perfiles iniciales Administrador, Operador y Consulta.
- Auditoría de inicio/cierre de sesión, fallos de autenticación, cambios administrativos y solicitudes de creación de equipos o conexiones.
- Navegación y control de acceso por permiso, con respuestas 401/403 y pantalla de acceso restringido.
- Pruebas unitarias para la inicialización de permisos, autenticación, validación de contraseñas, roles personalizados y auditoría.

### Changed

- README y contribución alineados al flujo `feature/*` → `develop` → `main`.
- Arquitectura, roadmap e integración NetBox ampliados y enlazados.
- Git, pip y Python de los despliegues se ejecutan como `sshtelenord`; systemd y comprobaciones operativas permanecen bajo root.
- El rollback informa si alguno de sus pasos requiere revisión manual.
- El prompt maestro de continuidad ahora es autocontenido.
- La autenticación deja de depender de una única sesión administrativa y usa cuentas persistentes; las variables `ADMIN_*` sirven para crear el administrador inicial si la base está vacía.
- La versión de aplicación por defecto avanza a `0.8.0`.

### Security

- Reglas explícitas para secretos, mínimo privilegio, separación de entornos y verificación previa.
- Protección contra despliegues con `.env` versionado o no ignorado.
- Rechazo de cambios locales, archivos no rastreados y propietarios inesperados antes de desplegar.
- Contraseñas almacenadas únicamente como hashes Argon2 y reglas mínimas de complejidad para cuentas nuevas.
- Protección para conservar al menos un administrador activo y evitar que un administrador desactive su propia cuenta.
- Base de datos local y directorio `data/` excluidos de Git; desarrollo y producción deben usar almacenamiento independiente.
