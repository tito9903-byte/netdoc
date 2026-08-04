# Integración con NetBox

NetBox es la **fuente oficial** del inventario; NetDoc no mantiene una copia
principal. Consume su API REST para lecturas de dispositivos, interfaces,
racks y cables, y para escrituras guiadas conocidas: creación de equipos,
cables, sites y pools IPAM protegidos por validación previa. NetBox conserva la
validación e integridad técnica final.

La ficha de un dispositivo consulta sus interfaces en DCIM y sus direcciones
en IPAM de forma concurrente. La solicitud de IPAM se limita por `device_id` y
las direcciones se relacionan con la fila correcta mediante
`assigned_object_id` o el ID del `assigned_object`. La IP principal del equipo
se mantiene como un atributo independiente: NetDoc no la deduce de la primera
dirección disponible.

La URL, token, tipo de token, verificación SSL y timeout se obtienen de `.env`.
`NETBOX_VERIFY_SSL` y `NETBOX_TIMEOUT` son configurables. Nunca versionar o
mostrar token. `NETBOX_WRITE_ENABLED` controla las rutas de escritura; en
desarrollo debe ser `false`.

Use tokens con permisos mínimos por operación, evite permisos amplios y rótelos
periódicamente y tras una exposición. Mantenga tokens y `.env` distintos por
entorno. Ante timeout, conexión o HTTP inválido, muestre un error controlado sin
secretos; investigue logs locales. Limitaciones: permisos exactos y esquema del
servidor requieren verificación. Mejoras planificadas: pruebas de integración,
validaciones avanzadas y auditoría.
