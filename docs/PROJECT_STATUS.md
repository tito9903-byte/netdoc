# Estado del proyecto: NetDoc

- **Propósito:** interfaz operativa para consultar, crear y visualizar inventario de red cuyo origen oficial es NetBox.
- **Estado general:** En progreso.
- **Última actualización:** 2026-08-06.
- **Versión documental:** 3.0.
- **Versión de aplicación de la rama:** 0.10.1.
- **Responsable / repositorio:** Luis Emilio García Pichardo / `tito9903-byte/netdoc`.
- **Ramas:** producción `main`; integración `develop`; trabajo documental en
  `docs/record-production-0.10.1`.

## Resumen ejecutivo

La versión `0.10.1` fue promovida a `main` mediante el PR #30, en el commit
`adb23925327e49090bb3be1bbbe74e1820650583`. Reúne Sites, conexiones por
lote, creación protegida de pools, gestión contextual de interfaces, mejoras de
racks, búsqueda y direcciones IPv4/IPv6 por interfaz. El propietario confirmó
el 2026-08-06 que el despliegue quedó funcionando en producción mediante el
servicio del puerto 8100.

Sites fue integrado en `develop` mediante el PR #13 y desplegado en desarrollo
en el commit `b85553346b5580ed37353d035168c0efec30befc`; el servicio terminó activo y
`/login` respondió HTTP 200. El propietario confirmó después la creación,
edición y retiro de un site y los permisos por rol.

El PR #14 eliminó el bloque redundante `Acciones rápidas` y fue integrado en
`develop` en `5e7d6cf4bf3529a40d909644067d67605acb666e`.

El PR #15 restauró el detalle profesional del rack sobre la base actual, sin
retirar Sites ni la navegación por módulos. Fue integrado en `develop` en
`a251b5d296896c8672531512f61589b54a8480df`, desplegado con la suite completa
superada y validado funcionalmente por el propietario en desarrollo.

El PR #16 integró `NETDOC.md` y las reglas persistentes de continuidad en
`develop`, que ahora parte de
`6e0d1dbe3ca8cb8237aacc2e1a5f03de0cb32351`.

El PR #17 corrigió dos regresiones detectadas por el propietario: el control
**Detalle ampliado** no ejecutaba ninguna acción y el catálogo de racks cargaba
todo el inventario de dispositivos y modelos. Fue integrado en `develop` en
`fbdb0c2db146a1e954d6bdc7ca1ceb6ff3ebae5d`, desplegado únicamente en
desarrollo y validado funcionalmente por el propietario. El
catálogo abre con agilidad, el detalle del rack carga y el selector **Rack
completo / Detalle ampliado** funciona. Producción permanece sin cambios.

El PR #23 restauró los enlaces internos al modelo y al rack desde la ficha del
dispositivo. Fue integrado en `develop` en
`4115bc7a2bf4d0f83fe053669d80870db06fad69`; el propietario confirmó en
desarrollo que ambos enlaces abren sus detalles internos.

La rama `fix/device-search-empty-filters` corrige la respuesta JSON de
validación que aparecía al buscar dispositivos sin seleccionar site o rol. Los
filtros vacíos o malformados se normalizan como no seleccionados, los IDs
válidos conservan su tipo entero y el navegador omite controles vacíos al
enviar el formulario. La selección aplicable superó 12/12 pruebas y la suite
aislada completa 133/133; el propietario confirmó la búsqueda sin filtros con
inventario real en desarrollo.

La rama `fix/ui-link-and-ipam-status` hace visibles como enlaces los valores de
modelo y rack desde su estado normal, sin depender del cursor, y corrige la
carga de estilos de Direccionamiento que podía dejar el estado de ocupación y
los filtros superpuestos por una hoja CSS anterior almacenada en caché. La
selección aplicable superó 15/15 pruebas y la suite aislada completa 135/135;
el propietario confirmó la corrección visual en desarrollo.

La rama `fix/ipam-status-dom-target` corrige la actualización del aviso de
ocupación después de la carga diferida. El selector anterior también alcanzaba
el punto indicador de 9 px y escribía allí la descripción completa, que se
mostraba verticalmente sobre los filtros. El título y la descripción usan ahora
selectores de datos inequívocos y el recurso JavaScript cambia de versión para
invalidar la copia anterior del navegador. La selección de IPAM superó 14/14
pruebas y la suite aislada completa 136/136; el propietario confirmó que el
estado diferido se presenta correctamente en desarrollo.

El PR #27 completó la ficha del dispositivo con las direcciones IPv4 e IPv6
asignadas a cada interfaz y fue integrado en `develop` en
`45f8a300f35f833cde353923edc0f0c931571400`. La vista consulta IPAM una sola
vez por dispositivo, limita la solicitud mediante `device_id`, asocia cada
dirección por `assigned_object_id` y conserva separada la IP principal
configurada en NetBox. Superó 4/4 pruebas específicas, 138/138 pruebas en la
suite aislada completa y `NetDoc CI`. El propietario confirmó con inventario
real en desarrollo que la columna **Direcciones IP** muestra las IP asignadas
a las interfaces del dispositivo. Producción no fue modificada.

El PR #19 contiene la creación de varias conexiones entre dos equipos en una
sola operación y evita que la consulta de cables recientes bloquee la apertura
inicial de la pantalla. El propietario confirmó con datos reales la apertura,
la creación del lote y la auditoría resultante en desarrollo.

El PR #21 integró la creación humana de pools desde Direccionamiento mediante
un plan revisable. Valida CIDR canónico,
duplicados dentro de la VRF, jerarquía, prefijo padre, bloques contenidos,
relaciones visibles y el contrato `OPTIONS` de NetBox antes del único `POST`.
También separa la apertura del catálogo del cálculo completo de ocupación:
prefijos y filtros aparecen primero, mientras direcciones y rangos se procesan
en segundo plano. El propietario confirmó en desarrollo la carga diferida, la
creación de un pool real y su resultado en NetBox.

El PR #20 integró en `develop`, en
`6843a353e74f0a9ee9300be6cb3e76865458fb42`, la eliminación del módulo
independiente **Plantillas de puertos** y concentró el generador masivo y el
inventario de interfaces dentro de la ficha del modelo correspondiente. Las
rutas antiguas se conservan como redirecciones compatibles. El propietario
confirmó en desarrollo la generación de interfaces y el inventario resultante.

## Entornos y servicios

| Entorno | Rama esperada | Aislamiento operativo |
|---|---|---|
| Producción | `main` | Ruta, servicio, endpoint y base independientes |
| Desarrollo | rama en revisión o `develop` | Ruta, servicio, endpoint y base independientes |

Estado actual confirmado:

- producción ejecuta la versión 0.10.1 de `main` en
  `adb23925327e49090bb3be1bbbe74e1820650583` y el propietario confirmó su
  funcionamiento en el puerto 8100;
- `develop` permanece en
  `24d2001159a567815def1f02679903f7c1e26df6`; no se realizó un nuevo
  despliegue de desarrollo durante esta promoción.

Las direcciones internas y los identificadores concretos de ejecución se
configuran fuera del repositorio público. La versión documentada de NetBox es
4.4.2.

## Arquitectura vigente

- FastAPI, Jinja2, HTTPX, Pydantic Settings, SessionMiddleware y Uvicorn.
- Pillow procesa las fotografías y ReportLab genera los reportes PDF del rack.
- NetBox conserva dispositivos, tipos, componentes, racks, sitios, cables, IPAM y demás inventario.
- SQLAlchemy conserva usuarios, roles, permisos, auditoría e imágenes de modelos propias de NetDoc.
- Alembic mantiene el esquema local; la cabeza de esta rama es `20260725_0002`.
- SQLite es el valor inicial de `DATABASE_URL`; cada entorno usa su propia base.
- Las escrituras hacia NetBox exigen autenticación, permiso, CSRF y `NETBOX_WRITE_ENABLED=true`.
- La escritura local de imágenes exige autenticación, permiso `devices.create` y CSRF, pero no modifica NetBox.
- Las imágenes se entregan mediante una ruta autenticada; el token de NetBox no se expone.
- Los cambios futuros de formularios e IA convergen en un `ChangePlan` determinista.

## Funcionalidades disponibles

- Dashboard, dispositivos, interfaces, filtros y paginación.
- Creación guiada de equipos.
- Consulta y creación de conexiones y cables.
- Racks con catálogo, detalle profesional y vista 3D.
- Ocupación física mediante posición, cara y `u_height`.
- Autenticación multiusuario, roles, permisos, perfil y auditoría.
- Protección temporal de inicio de sesión.
- Búsqueda global y módulo Sistema.
- Direccionamiento IP con pools, localidad, VRF y ocupación.
- En la rama actual, alta protegida de pools con vista previa, confirmación
  ligada al plan, auditoría y revalidación inmediata antes de escribir.
- Fabricantes, modelos, ficha completa y componentes reutilizables.
- Generación masiva de interfaces dentro de la ficha del modelo responsable.
- Creación de modelos con imágenes opcionales.
- Planes seguros, lista cerrada de capacidades y vista previa de cables.
- Sites con catálogo, filtros y operaciones controladas.
- Inventario del rack con dispositivo, modelo, posición/cara, serial, IP
  principal, estado, búsqueda y acceso a la ficha.
- Reporte PDF descargable del rack en una sola página, con elevación 3D,
  fotografías e inventario.

## Integrado en `develop`

### Gestión de Sites

- Catálogo con búsqueda y filtro por estado.
- Creación y edición de nombre, código, estado, facilidad, direcciones, coordenadas y descripción.
- Retiro mediante cambio de estado; no se eliminan sites.
- Validación de nombre o código duplicado antes de escribir.
- Permisos `sites.view` y `sites.manage`; la gestión queda reservada al Administrador por defecto.
- CSRF, modo de escritura, auditoría y errores controlados.
- NetBox continúa como fuente oficial; no se duplica el objeto Site en la base local.

### Persistencia local de imágenes

- Tabla `device_type_images` mediante migración `20260725_0002`.
- Una imagen frontal y una trasera por `device_type_id`.
- Sustitución idempotente por la restricción única `(device_type_id, face)`.
- Validación de JPG, PNG, WEBP y GIF mediante firma binaria real.
- Límite de 5 MB por archivo.
- Hash SHA-256, nombre seguro, tamaño, fecha y usuario de actualización.
- Consultas de catálogo que recuperan solo metadatos, no binarios.
- Lectura local prioritaria y fallback a imágenes antiguas de NetBox.
- Entrega autenticada con `ETag`, caché privada y `nosniff`.
- Reutilización en catálogo, ficha, rack 2D y rack 3D.

### Migraciones y compatibilidad

- Las bases vacías reciben `0001` y `0002`.
- Las bases versionadas se actualizan hasta `head`.
- Una base heredada completa del esquema inicial se marca en `20260724_0001` y después recibe `0002`.
- Los esquemas parciales siguen siendo rechazados.

### Seguridad

- No se escribe en `MEDIA_ROOT` de NetBox.
- No se almacena el token de NetBox en la base de imágenes.
- La ruta de carga valida sesión, permiso y CSRF.
- Antes de guardar se comprueba que el modelo todavía existe en NetBox.
- Los errores SQL se convierten en mensajes controlados.
- Las imágenes pasan a formar parte del respaldo de `DATABASE_URL`.

## Validaciones automatizadas disponibles

- compilación Python;
- grafo Alembic con una sola cabeza;
- creación y actualización de la tabla local;
- adopción de una base heredada completa;
- guardado, sustitución y lectura de imágenes;
- rechazo de archivos cuya firma no corresponde a una imagen;
- prioridad de la imagen local sobre NetBox;
- carga multipart autenticada y entrega de la imagen;
- importación de la aplicación y análisis de plantillas;
- suite aislada sobre una base temporal.
- permisos, validaciones y rutas del módulo Sites.
- estructura, contenido y búsqueda del inventario del rack;
- generación y descarga autenticada del reporte PDF;
- fotografías del rack a `width: 100%`, `height: 100%` y `object-fit: fill`.
- cambio real y persistencia local de la escala **Rack completo / Detalle ampliado**;
- catálogo de racks sin carga global de dispositivos ni consultas de modelos;
- reutilización de un mismo cliente HTTP y su pool por solicitud del módulo de
  racks.
- apertura de Conexiones sin esperar sites, opciones ni cables recientes;
- carga diferida del historial y carga paralela de los datos iniciales;
- creación por lote de hasta 50 pares de interfaces entre dos equipos;
- rechazo de interfaces repetidas dentro del lote y un único POST masivo hacia
  NetBox.
- apertura de Direccionamiento sin descargar primero todas las direcciones y
  rangos IP;
- cálculo diferido de ocupación con actualización de la tabla y los KPI;
- CIDR canónico, duplicado por VRF, padre, hijos y solapamientos de pools;
- contrato `OPTIONS`, capacidad registrada, CSRF, permiso, modo de escritura,
  confirmación inmutable y un solo POST al crear un pool.
- ausencia del acceso independiente **Plantillas de puertos** en la navegación;
- redirección de enlaces antiguos hacia la sección de interfaces del modelo;
- generador masivo e inventario de puertos renderizados en la ficha del modelo.
- enlaces internos del modelo y rack desde la ficha del dispositivo, con texto
  no interactivo cuando NetBox no entrega el ID correspondiente.
- búsqueda de dispositivos con filtros vacíos, válidos y malformados sin
  exponer respuestas JSON de validación de FastAPI.
- señalización visual persistente de los enlaces internos de modelo y rack;
- distribución propia del estado de ocupación de IPAM y versión renovada de su
  hoja de estilos para evitar superposición con los filtros.
- destino explícito del título y la descripción del estado de IPAM para impedir
  que el texto de finalización se inserte dentro del punto indicador.
- consulta acotada de direcciones IP por dispositivo, asociación a interfaces
  físicas mediante el objeto asignado y presentación de varias IPv4/IPv6.

## Validado funcionalmente en desarrollo

- creación, edición y retiro de Sites y permisos por rol;
- apertura y creación por lote de Conexiones con auditoría;
- creación de un pool real comprobado en NetBox;
- generación de interfaces dentro del modelo y verificación del inventario;
- enlaces internos de modelo y rack, búsqueda sin filtros y correcciones
  visuales de IPAM.

## Requiere verificación en desarrollo

- confirmar `alembic current` y `alembic heads` en `20260725_0002` después del
  próximo despliegue de código;
- cargar una imagen en un modelo existente;
- confirmar la etiqueta **Guardada en NetDoc**;
- revisar la misma imagen en catálogo, ficha, rack 2D y rack 3D;
- sustituirla y comprobar el cambio de `ETag`;
- revisar el evento de auditoría;
- confirmar que NetBox no recibió un `PATCH` de imagen.
- revisar los eventos `SITE_CREATE`, `SITE_UPDATE` y `SITE_DEACTIVATE`;
- confirmar que no aparece `Acciones rápidas` y que las altas siguen dentro de
  cada módulo;
- comprobar con un token limitado que un duplicado exacto no escribe y revisar
  el evento `IPAM_POOL_CREATE`;
- comprobar que el enlace antiguo de plantillas redirige a la sección de
  interfaces del modelo.

## Riesgos y deuda

- Las imágenes aumentan el tamaño de la base local; el respaldo y el espacio libre deben supervisarse.
- SQLite es adecuado para el tamaño inicial, pero debe reevaluarse antes de varios workers o miles de modelos.
- El `device_type_id` es una referencia externa: una futura eliminación de modelos necesitará limpieza controlada de imágenes huérfanas.
- La creación del modelo en NetBox y el guardado local de imágenes no forman una única transacción.
- El rollback de código no revierte migraciones ni restaura la base.
- Aún faltan editores propios para bahías de módulos, energía, consola y patch panels.
- El asistente conversacional todavía no tiene interfaz ni ejecutor habilitado.

## Próximo objetivo

Completar las verificaciones operativas todavía pendientes: imágenes de
modelos en catálogo y racks, eventos de auditoría específicos, navegación sin
accesos duplicados y compatibilidad de redirecciones antiguas. La imagen
representativa del site queda diferida hasta definir almacenamiento, respaldo y
asociación sin duplicar el inventario oficial.

## Reglas de mantenimiento

`NETDOC.md` es el punto de entrada para todo chat nuevo y `AGENTS.md` contiene
las instrucciones persistentes. El flujo oficial es modificar, probar, crear el commit,
publicar la rama, verificar el SHA remoto, abrir PR hacia `develop`, desplegar
únicamente desarrollo con autorización, realizar la revisión y tocar producción
solo después de una autorización explícita. Las pruebas específicas y completas
se ejecutan mediante `scripts/netdoc-test-isolated`; los servidores solo
descargan commits remotos verificados y no reconstruyen ni publican historial.
La navegación principal no debe duplicar acciones: cada creación comienza
dentro del módulo responsable. Después de la confirmación funcional del
propietario, el agente actualiza `NETDOC.md` mediante PR con el resultado real,
SHA, pruebas, estado de los entornos y pendientes.

Actualizar este documento en todo PR que modifique funcionalidad, arquitectura, seguridad, despliegue, dependencias, pruebas, riesgos o prioridades. Estados permitidos: **Completado**, **En progreso**, **Planificado**, **Bloqueado**, **Diferido** y **Requiere verificación**.
