# Estado del proyecto: NetDoc

- **Propósito:** interfaz operativa para consultar, crear y visualizar inventario de red cuyo origen oficial es NetBox.
- **Estado general:** En progreso.
- **Última actualización:** 2026-08-04.
- **Versión documental:** 3.0.
- **Versión de aplicación de la rama:** 0.10.1.
- **Responsable / repositorio:** Luis Emilio García Pichardo / `tito9903-byte/netdoc`.
- **Ramas:** producción `main`; integración `develop`; trabajo documental en
  `docs/validate-device-interface-ips`.

## Resumen ejecutivo

La versión `0.10.0` fue promovida a `main` y reúne autenticación, roles, auditoría, búsqueda, Sistema, IPAM, fabricantes, modelos, plantillas, conexiones, racks 2D/3D y la base segura para el futuro asistente.

Sites fue integrado en `develop` mediante el PR #13 y desplegado en desarrollo
en el commit `b85553346b5580ed37353d035168c0efec30befc`; el servicio terminó activo y
`/login` respondió HTTP 200. La revisión funcional completa del módulo sigue
pendiente.

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
`4115bc7a2bf4d0f83fe053669d80870db06fad69`; la revisión funcional en
desarrollo sigue pendiente.

La rama `fix/device-search-empty-filters` corrige la respuesta JSON de
validación que aparecía al buscar dispositivos sin seleccionar site o rol. Los
filtros vacíos o malformados se normalizan como no seleccionados, los IDs
válidos conservan su tipo entero y el navegador omite controles vacíos al
enviar el formulario. La selección aplicable superó 12/12 pruebas y la suite
aislada completa 133/133; la revisión funcional en desarrollo sigue pendiente.

La rama `fix/ui-link-and-ipam-status` hace visibles como enlaces los valores de
modelo y rack desde su estado normal, sin depender del cursor, y corrige la
carga de estilos de Direccionamiento que podía dejar el estado de ocupación y
los filtros superpuestos por una hoja CSS anterior almacenada en caché. La
selección aplicable superó 15/15 pruebas y la suite aislada completa 135/135;
la revisión visual en desarrollo sigue pendiente.

La rama `fix/ipam-status-dom-target` corrige la actualización del aviso de
ocupación después de la carga diferida. El selector anterior también alcanzaba
el punto indicador de 9 px y escribía allí la descripción completa, que se
mostraba verticalmente sobre los filtros. El título y la descripción usan ahora
selectores de datos inequívocos y el recurso JavaScript cambia de versión para
invalidar la copia anterior del navegador. La selección de IPAM superó 14/14
pruebas y la suite aislada completa 136/136; la revisión visual en desarrollo
sigue pendiente.

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
inicial de la pantalla. Su validación funcional en desarrollo sigue pendiente.

La rama `feature/ipam-pool-workspace` habilita la creación humana de pools
desde Direccionamiento mediante un plan revisable. Valida CIDR canónico,
duplicados dentro de la VRF, jerarquía, prefijo padre, bloques contenidos,
relaciones visibles y el contrato `OPTIONS` de NetBox antes del único `POST`.
También separa la apertura del catálogo del cálculo completo de ocupación:
prefijos y filtros aparecen primero, mientras direcciones y rangos se procesan
en segundo plano. Esta función todavía no ha sido integrada ni validada en
desarrollo.

El PR #20 integró en `develop`, en
`6843a353e74f0a9ee9300be6cb3e76865458fb42`, la eliminación del módulo
independiente **Plantillas de puertos** y concentró el generador masivo y el
inventario de interfaces dentro de la ficha del modelo correspondiente. Las
rutas antiguas se conservan como redirecciones compatibles. La revisión
funcional en desarrollo sigue pendiente.

## Entornos y servicios

| Entorno | Rama esperada | Aislamiento operativo |
|---|---|---|
| Producción | `main` | Ruta, servicio, endpoint y base independientes |
| Desarrollo | rama en revisión o `develop` | Ruta, servicio, endpoint y base independientes |

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

## Requiere verificación en desarrollo

- confirmar `alembic current` y `alembic heads` en `20260725_0002`;
- cargar una imagen en un modelo existente;
- confirmar la etiqueta **Guardada en NetDoc**;
- revisar la misma imagen en catálogo, ficha, rack 2D y rack 3D;
- sustituirla y comprobar el cambio de `ETag`;
- revisar el evento de auditoría;
- confirmar que NetBox no recibió un `PATCH` de imagen.
- crear, editar y retirar un site de prueba en desarrollo;
- confirmar permisos de Administrador, Operador y Consulta;
- revisar los eventos `SITE_CREATE`, `SITE_UPDATE` y `SITE_DEACTIVATE`.
- confirmar que no aparece `Acciones rápidas`;
- comprobar que crear equipos, racks y sites sigue disponible dentro de cada
  módulo y que ninguna ruta de creación fue eliminada.
- medir la apertura de Conexiones con el inventario real;
- crear varias filas entre dos equipos y comprobar etiquetas individuales;
- confirmar que una interfaz usada desaparece de las demás filas;
- validar que un lote real crea exactamente todos los cables solicitados y
  genera auditoría controlada.
- medir la apertura de Direccionamiento con el inventario IPAM real;
- revisar que los KPI y cada fila se completen después de la carga inicial;
- validar un pool nuevo primero en vista previa y confirmar VRF, localidad,
  rol, padre, hijos y advertencias;
- comprobar con un token limitado que un duplicado exacto no escribe y que un
  pool válido crea un solo prefijo con `is_pool=true`;
- revisar el cambio en NetBox y el evento `IPAM_POOL_CREATE` en Auditoría.
- confirmar que **Plantillas de puertos** no aparece como módulo independiente;
- abrir un modelo y validar generación, vista previa e inventario de interfaces
  dentro de la misma ficha;
- comprobar que un enlace antiguo `/interface-templates?device_type_id=<id>`
  redirige a `/device-types/<id>#interfaces`.
- abrir un dispositivo con modelo y rack asignados, comprobar que ambos valores
  son enlaces y confirmar que el rack entra directamente en su detalle 3D.
- buscar un dispositivo sin seleccionar site, rol ni estado y confirmar que la
  lista HTML abre sin parámetros vacíos ni respuesta JSON de validación.

## Riesgos y deuda

- Las imágenes aumentan el tamaño de la base local; el respaldo y el espacio libre deben supervisarse.
- SQLite es adecuado para el tamaño inicial, pero debe reevaluarse antes de varios workers o miles de modelos.
- El `device_type_id` es una referencia externa: una futura eliminación de modelos necesitará limpieza controlada de imágenes huérfanas.
- La creación del modelo en NetBox y el guardado local de imágenes no forman una única transacción.
- El rollback de código no revierte migraciones ni restaura la base.
- Aún faltan editores propios para bahías de módulos, energía, consola y patch panels.
- El asistente conversacional todavía no tiene interfaz ni ejecutor habilitado.

## Próximo objetivo

Validar en desarrollo la búsqueda de dispositivos con filtros vacíos y los
accesos al modelo y al rack. Continúan pendientes la validación real de un pool,
la validación funcional del PR #20 para la
gestión contextual de interfaces, la validación del PR #19 de Conexiones y la
revisión completa de Sites. La imagen representativa del site queda diferida
hasta definir almacenamiento, respaldo y asociación sin duplicar el inventario
oficial.

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
