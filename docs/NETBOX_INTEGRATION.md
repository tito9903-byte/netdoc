# Integración con NetBox

NetBox es la **fuente oficial** del inventario; NetDoc no mantiene una copia
principal. Consume su API REST para lecturas de dispositivos, interfaces,
racks y cables, y para escrituras guiadas conocidas: creación de equipos,
cables, sites y pools IPAM protegidos por validación previa. NetBox conserva la
validación e integridad técnica final.

La URL, token, tipo de token, verificación SSL y timeout se obtienen de `.env`.
`NETBOX_VERIFY_SSL` y `NETBOX_TIMEOUT` son configurables. Nunca versionar o
mostrar token. `NETBOX_WRITE_ENABLED` controla las rutas de escritura; en
todos los entornos su valor predeterminado debe ser `false`. Puede habilitarse
por entorno únicamente con autorización expresa y sin omitir permisos, CSRF,
validación, confirmación ni auditoría. Desarrollo tiene esa excepción desde
2026-08-03 para pruebas funcionales controladas; producción no fue modificada.

Use tokens con permisos mínimos por operación, evite permisos amplios y rótelos
periódicamente y tras una exposición. Mantenga tokens y `.env` distintos por
entorno. Ante timeout, conexión o HTTP inválido, muestre un error controlado sin
secretos; investigue logs locales. Limitaciones: permisos exactos y esquema del
servidor requieren verificación. Mejoras planificadas: pruebas de integración,
validaciones avanzadas y auditoría.
