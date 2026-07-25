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
- Perfil de autoservicio para editar nombre, correo y contraseña propia.
- Protección temporal configurable contra fallos repetidos de inicio de sesión por usuario e IP.
- Auditoría de inicio y cierre de sesión, fallos, bloqueos temporales, cambios administrativos y solicitudes de creación de equipos o conexiones.
- Navegación y control de acceso por permiso, con respuestas 401/403 y pantalla de acceso restringido.
- Pruebas unitarias y de rutas para inicialización, autenticación, permisos, auditoría, revocación, cambios de rol, perfil y bloqueo de login.
- Workflow de GitHub Actions para dependencias, compilación, grafo de migraciones, pruebas, importación, plantillas y scripts.
- Búsqueda global simultánea de dispositivos, interfaces, racks, sitios y cables.
- Módulo Sistema de solo lectura con CPU, RAM, disco, red, uptime y datos del proceso.
- Filtros de usuarios por texto, rol y estado, con eliminación controlada de cuentas.
- Auditoría con filtros por recurso y fechas, paginación preservada y exportación CSV protegida.
- Migración inicial Alembic `20260724_0001` para permisos, roles, usuarios y auditoría.
- Adopción segura de bases heredadas completas y rechazo de esquemas parciales.
- Pruebas automatizadas de creación, actualización idempotente y adopción del esquema.
- Módulo de direccionamiento IP con prefijos, pools, localidad, VRF, rol, capacidad, disponibilidad y ocupación.
- Clasificación de pools saludables, en advertencia, críticos y llenos.
- Catálogo de modelos de dispositivo y consulta de plantillas de interfaz.
- Generación masiva de hasta 256 interfaces a partir de patrones con vista previa interactiva.
- Creación guiada de modelos de dispositivo protegida por permiso, CSRF y modo de escritura.
- Carga opcional de imágenes frontal y trasera en el mismo formulario de creación del modelo.
- Galería posterior para sustituir imágenes del modelo sin recrear sus plantillas.
- Proxy autenticado para mostrar imágenes privadas de NetBox sin exponer el token.
- Vista 3D integrada en el detalle del rack con selector 2D/3D y cambio de cara.
- Ocupación de rack basada en `u_height`, incluida media unidad, equipos 0U y detección de conflictos.
- Creación guiada de racks con sitio, ubicación, capacidad, ancho, numeración, estado, rol e identificadores físicos.
- Pruebas para patrones de interfaces, normalización de slug, capacidad/localidad IPAM, imágenes y presentación física de racks.
- Guía versionada para modelos, imágenes y vistas físicas de racks.

### Changed

- README y contribución alineados al flujo `feature/*` → `develop` → `main`.
- Arquitectura, roadmap e integración NetBox ampliados y enlazados.
- Git, pip y Python de los despliegues se ejecutan como `sshtelenord`; systemd y comprobaciones operativas permanecen bajo root.
- El rollback informa si alguno de sus pasos requiere revisión manual.
- El prompt maestro de continuidad ahora es autocontenido.
- La autenticación deja de depender de una única sesión administrativa y usa cuentas persistentes; las variables `ADMIN_*` sirven para crear el administrador inicial si la base está vacía.
- La identidad, el estado de la cuenta, el rol y los permisos se recargan desde la base antes de cada solicitud protegida.
- La desactivación de una cuenta y los cambios de permisos se aplican en la siguiente solicitud.
- La inicialización del esquema deja de depender de `create_all` y utiliza Alembic durante el arranque.
- La navegación se reorganiza alrededor de flujos de documentación y separa General, Documentación, Acciones rápidas y Administración.
- Topología 3D deja de ocupar una opción independiente del menú y pasa a seleccionarse dentro de cada rack.
- El dashboard funciona como centro de inicio para IPAM, modelos, racks y conexiones.
- La búsqueda global ofrece accesos directos a los flujos principales cuando no existe una consulta.
- La pantalla de creación de equipo explica la relación entre modelo, interfaces, ubicación y elevación.
- El formulario de creación del modelo reúne dimensiones e imágenes físicas en una sola operación.
- El listado de racks deja de presentar ocupación `0.0%` cuando NetBox no devuelve un valor calculado.
- El ancho de rack se renderiza correctamente cuando la API devuelve una opción estructurada.
- La pantalla de conexiones diferencia claramente modo de escritura y vista previa de solo lectura.
- Las pantallas administrativas alinean acciones, estados y tablas.
- La versión de aplicación por defecto avanza a `0.10.0`.

### Security

- Reglas explícitas para secretos, mínimo privilegio, separación de entornos y verificación previa.
- Protección contra despliegues con `.env` versionado o no ignorado.
- Rechazo de cambios locales, archivos no rastreados y propietarios inesperados antes de desplegar.
- Contraseñas almacenadas únicamente como hashes Argon2 y reglas mínimas de complejidad para cuentas nuevas.
- El cambio de contraseña propia exige verificar la contraseña actual y nunca registra credenciales en auditoría.
- Cinco fallos recientes del mismo usuario y la misma IP producen HTTP 429 con `Retry-After`; los límites son configurables.
- Protección para conservar al menos un administrador activo y evitar que un administrador desactive su propia cuenta.
- Revocación efectiva de cuentas desactivadas sin esperar un nuevo inicio de sesión.
- Base de datos local y directorio `data/` excluidos de Git; desarrollo y producción deben usar almacenamiento independiente.
- Exportación CSV protegida contra fórmulas de hoja de cálculo y limitada a 10,000 eventos.
- El módulo Sistema usa únicamente lecturas no privilegiadas y no ejecuta comandos de administración.
- El arranque falla ante esquemas locales parciales en lugar de crear silenciosamente tablas faltantes.
- Las creaciones de modelos, interfaces, imágenes y racks requieren autenticación, autorización, CSRF y escritura habilitada.
- Los archivos de imagen se validan por tipo y tamaño antes de crear o actualizar el modelo.
- Desarrollo conserva los botones de escritura deshabilitados y muestra el modo de solo lectura de forma explícita.
- El menú móvil mantiene `aria-expanded`, admite cierre con Escape y devuelve el foco al control de apertura.