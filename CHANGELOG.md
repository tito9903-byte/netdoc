# Changelog

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las futuras versiones seguirán Semantic Versioning.

## Unreleased

### Added

- Creación por lote de hasta 50 conexiones entre dos equipos, con una fila por
  pareja de interfaces y etiqueta individual.
- Inventario profesional debajo de la elevación del rack con dispositivo,
  modelo, posición/cara, serial, IP principal, estado, búsqueda y acceso a la
  ficha.
- Reporte PDF descargable del rack en una sola página con elevación 3D,
  fotografías e inventario.
- Módulo de Sites con catálogo, filtros, alta, edición y retiro controlado sobre NetBox.
- Permisos separados `sites.view` y `sites.manage`, validación de duplicados, CSRF y auditoría.
- Dashboard conectado a NetBox.
- Consulta y detalle de dispositivos.
- Creación guiada de equipos.
- Conexiones entre interfaces.
- Visualización de racks en 2D.
- Inicio de sesión administrativo.
- Documentación inicial del proyecto.
- Índice documental, estado vivo, prompt de continuidad, glosario, pruebas y documentación operativa.
- ADR sobre plataforma dedicada, separación de entornos, NetBox, documentación como código, identidad local y planes seguros.
- Scripts independientes de despliegue para desarrollo y producción con comprobaciones y rollback.
- Bloqueo de despliegues simultáneos con `flock`.
- Verificación de `.env`, árbol Git limpio, propietarios y archivo de dependencias antes de actualizar.
- Comprobación HTTP con reintentos y aceptación de HTTP 200 o cualquier 3xx.
- Persistencia local configurable con SQLAlchemy para identidades, roles, permisos y auditoría.
- Gestión de usuarios: creación, edición, activación, asignación de rol y restablecimiento de contraseña.
- Gestión de roles y permisos con perfiles iniciales Administrador, Operador y Consulta.
- Perfil de autoservicio para editar nombre, correo y contraseña propia.
- Protección temporal configurable contra fallos repetidos de inicio de sesión por usuario e IP.
- Auditoría de inicio y cierre de sesión, fallos, bloqueos temporales y cambios administrativos.
- Navegación y control de acceso por permiso, con respuestas 401/403 y pantalla de acceso restringido.
- Workflow de GitHub Actions para dependencias, compilación, grafo de migraciones, pruebas, importación, plantillas y scripts.
- Búsqueda global simultánea de dispositivos, interfaces, racks, sitios y cables.
- Módulo Sistema de solo lectura con CPU, RAM, disco, red, uptime y datos del proceso.
- Auditoría con filtros por recurso y fechas, paginación y exportación CSV protegida.
- Migración inicial Alembic `20260724_0001` y adopción segura de bases heredadas completas.
- Migración `20260725_0002` para almacenar imágenes frontal y trasera de modelos en la base local de NetDoc.
- Módulo de direccionamiento IP con prefijos, pools, localidad, VRF, rol, capacidad, disponibilidad y ocupación.
- Clasificación de pools saludables, en advertencia, críticos y llenos.
- Catálogo de modelos y consulta de plantillas de interfaces.
- Generación masiva de hasta 256 interfaces mediante patrones y vista previa.
- Creación guiada de modelos protegida por permiso, CSRF y modo de escritura.
- Carga opcional de imágenes frontal y trasera al crear el modelo.
- Galería para sustituir imágenes sin recrear el modelo.
- Almacenamiento local de imágenes con validación por firma, límite de 5 MB, hash SHA-256 y asociación al `device_type_id` de NetBox.
- Fallback de lectura para imágenes ya existentes en NetBox.
- Entrega autenticada de imágenes con ETag y caché privada para racks 2D/3D.
- Vista 3D integrada en el detalle del rack con selector 2D/3D y cambio de cara.
- Ocupación de rack basada en `u_height`, incluida media unidad, equipos 0U y conflictos.
- Creación guiada de racks con sitio, ubicación, capacidad, ancho, numeración, estado y rol.
- Apartado independiente de fabricantes con catálogo, creación, ficha y edición controlada.
- Ficha completa por modelo con edición, imágenes, resumen de componentes, interfaces y equipos asociados.
- Navegación separada para Fabricantes y Modelos de equipos.
- `ChangePlan` con pasos, dependencias, advertencias, huella SHA-256 y confirmación ligada al plan.
- Redacción recursiva de tokens, secretos y contraseñas antes de mostrar o registrar planes.
- Lista cerrada de capacidades REST conocidas y rechazo inicial de operaciones `DELETE`.
- Descubrimiento del esquema instalado mediante `OPTIONS` y validación dinámica de campos y opciones.
- Planificador determinista de cables que valida extremos, ocupación, color y longitud.
- API de solo vista previa `POST /api/change-plans/cable`; consulta interfaces reales y no escribe.
- Mapa de cobertura de módulos de NetBox y arquitectura del futuro asistente conversacional.
- Pruebas para hardware, planes, confirmación, allowlist, esquemas `OPTIONS`, imágenes locales y vista previa de cables.

### Changed

- La gestión de interfaces deja de ser un módulo independiente: el generador
  masivo y el inventario se concentran en la ficha de cada modelo, y las rutas
  antiguas redirigen a la sección de puertos del modelo correspondiente.
- La pantalla de Conexiones se muestra sin esperar respuestas de NetBox; carga
  sites y opciones en segundo plano y consulta el historial después del
  formulario.
- Las consultas de cada operación de Conexiones reutilizan un cliente HTTP y su
  pool, y la creación múltiple envía un único POST masivo a NetBox.
- El documento maestro de continuidad pasa a llamarse `NETDOC.md`, queda en la
  raíz y registra únicamente como terminados los cambios confirmados por el
  propietario en desarrollo.
- Se restaura la línea completa de mejoras del rack sobre el `develop` actual
  para conservar Sites y la navegación por módulos.
- Pillow y ReportLab quedan declarados y bloqueados como dependencias del
  reporte PDF.
- Las fotografías de equipos ocupan exactamente el área física asignada con
  `width: 100%`, `height: 100%` y `object-fit: fill`, sin reglas posteriores
  `contain` o `cover`.
- `AGENTS.md` formaliza el flujo persistente para futuros chats: inspección
  previa, pruebas completas, commits creados por el agente, publicación con SHA
  remoto verificado, PR hacia `develop`, despliegue aislado en 8101 y
  producción únicamente con autorización explícita.
- La navegación principal queda limitada a módulos; cada alta se inicia desde
  el catálogo o detalle correspondiente y se elimina el bloque redundante de
  `Acciones rápidas`.
- Las pruebas selectivas ahora se ejecutan mediante
  `scripts/netdoc-test-isolated <módulos>` con base y credenciales desechables.
- GitHub Actions utiliza y valida el mismo ejecutor aislado que el flujo local.
- El flujo de agentes y despliegue prohíbe reconstruir o publicar commits desde
  el servidor; desarrollo y producción solo consumen referencias remotas
  verificadas y se detienen ante cualquier validación fallida.
- README, roadmap, estado y documentación alineados al flujo `feature/*` → `develop` → `main`.
- Git, pip y Python de los despliegues se ejecutan como `sshtelenord`; systemd permanece bajo root.
- La autenticación usa cuentas persistentes y recarga identidad y permisos antes de cada solicitud protegida.
- La inicialización del esquema utiliza Alembic y rechaza esquemas parciales.
- Las bases heredadas completas se marcan en `20260724_0001` y luego reciben migraciones posteriores, en vez de marcarse directamente en `head`.
- La navegación se organiza alrededor de General, Documentación y Administración.
- Fabricantes y modelos conservan apartados propios; las interfaces se gestionan dentro de la ficha del modelo responsable.
- Crear modelo se inicia desde el catálogo de modelos.
- Topología 3D deja de ocupar una opción independiente y se selecciona dentro de cada rack.
- El dashboard funciona como centro de inicio para IPAM, hardware, racks y conexiones.
- El formulario de creación del modelo reúne dimensiones e imágenes físicas.
- La ficha del modelo se convierte en el centro para información, imágenes, componentes y equipos asociados.
- Las nuevas imágenes de modelos ya no dependen de permisos de escritura sobre `MEDIA_ROOT` de NetBox; se guardan en NetDoc.
- La pantalla de conexiones diferencia modo de escritura y vista previa de solo lectura.
- La arquitectura del futuro chat separa interpretación, resolución, planificación, políticas, confirmación y ejecución.
- La versión de aplicación por defecto avanza a `0.10.1`.

### Fixed

- El control **Detalle ampliado** vuelve a cambiar la escala real de la vista 3D
  y conserva la preferencia en el navegador.
- El catálogo de racks deja de descargar todos los dispositivos y consultar
  cada modelo; carga únicamente sites y racks, y reserva ocupación, imágenes y
  conflictos para el detalle seleccionado.
- Las consultas de una misma página del módulo de racks reutilizan el cliente
  HTTP hacia NetBox y cierran el pool al terminar.

### Security

- Reglas explícitas para secretos, mínimo privilegio, separación de entornos y verificación previa.
- Protección contra despliegues con `.env` versionado o no ignorado.
- Rechazo de cambios locales, archivos no rastreados y propietarios inesperados antes de desplegar.
- Contraseñas almacenadas únicamente como hashes Argon2.
- Bloqueo temporal de login y revocación efectiva de cuentas desactivadas.
- Base local y directorio `data/` excluidos de Git.
- Exportación CSV protegida contra fórmulas y limitada a 10,000 eventos.
- Las escrituras hacia NetBox requieren autenticación, autorización, CSRF y `NETBOX_WRITE_ENABLED=true`.
- La escritura de imágenes locales exige sesión, permiso `devices.create` y CSRF, pero no modifica NetBox.
- Los archivos de imagen se validan por tipo declarado, firma real, tamaño y nombre seguro.
- El token de NetBox no se expone al navegador ni a planes públicos.
- La IA futura no podrá inventar endpoints, métodos, permisos, IDs ni payloads ejecutables.
- Los planes automáticos no admiten eliminaciones en la primera etapa.
- La confirmación queda ligada a la huella exacta del plan revisado.
- Desarrollo conserva escritura hacia NetBox deshabilitada y producción no se modifica durante la revisión.