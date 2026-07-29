# Estado del proyecto: NetDoc

- **Propósito:** interfaz operativa para consultar, crear y visualizar inventario de red cuyo origen oficial es NetBox.
- **Estado general:** En progreso.
- **Última actualización:** 2026-07-25.
- **Versión documental:** 2.3.
- **Versión de aplicación de la rama:** 0.10.1.
- **Responsable / repositorio:** Luis Emilio García Pichardo / `tito9903-byte/netdoc`.
- **Ramas:** producción `main`; integración `develop`; trabajo actual `feature/rack-image-containment`.

## Resumen ejecutivo

La versión `0.10.0` fue promovida a `main` y reúne autenticación, roles, auditoría, búsqueda, Sistema, IPAM, fabricantes, modelos, plantillas, conexiones, racks 2D/3D y la base segura para el futuro asistente.

`develop` ya contiene el almacenamiento local de imágenes de modelos mediante la migración `20260725_0002`. La rama actual mejora la representación física del rack: fotografías sin deformación, gabinete 3D estilo datacenter, escala detallada, reemplazo visible de imágenes y reporte PDF descargable con inventario.

## Entornos y servicios

| Entorno | Ruta | Rama esperada | Servicio | Puerto | Escrituras |
|---|---|---|---|---:|---|
| Producción | `/opt/netdoc-prod` | `main` | `netdoc-prod` | 8100 | solo funciones validadas y promovidas |
| Desarrollo | `/opt/netdoc-dev` | rama en revisión o `develop` | `netdoc-dev` | 8101 | habilitadas para pruebas manuales controladas |
| Pruebas automatizadas | base temporal | commit evaluado | proceso aislado | no aplica | `NETBOX_WRITE_ENABLED=false` |

Servidor dedicado: `192.168.10.93`. NetBox: `https://192.168.10.95`, versión documentada 4.4.2.

Desarrollo es el entorno donde se prueban creaciones y modificaciones reales antes de producción. La suite automatizada permanece aislada, utiliza una base temporal y no puede escribir en NetBox.

## Arquitectura vigente

- FastAPI, Jinja2, HTTPX, Pydantic Settings, SessionMiddleware y Uvicorn.
- NetBox conserva dispositivos, tipos, componentes, racks, sitios, cables, IPAM y demás inventario.
- SQLAlchemy conserva usuarios, roles, permisos, auditoría e imágenes de modelos propias de NetDoc.
- Alembic mantiene el esquema local; la cabeza actual es `20260725_0002`.
- SQLite es el valor inicial de `DATABASE_URL`; cada entorno usa su propia base.
- Las escrituras hacia NetBox exigen autenticación, permiso, CSRF y `NETBOX_WRITE_ENABLED=true`.
- La escritura local de imágenes exige autenticación, permiso `devices.create` y CSRF, pero no modifica NetBox.
- Las imágenes se entregan mediante una ruta autenticada con ETag; el token de NetBox no se expone.
- Los reportes PDF se generan bajo demanda mediante primitivas internas y no se almacenan.
- Los cambios futuros de formularios e IA convergen en un `ChangePlan` determinista.

## Funcionalidades disponibles en `develop`

- Dashboard, dispositivos, interfaces, filtros y paginación.
- Creación guiada de equipos.
- Consulta y creación de conexiones y cables.
- Racks con listado, detalle, elevación 2D y vista 3D.
- Ocupación física mediante posición, cara y `u_height`.
- Autenticación multiusuario, roles, permisos, perfil y auditoría.
- Protección temporal de inicio de sesión.
- Búsqueda global y módulo Sistema.
- Direccionamiento IP con pools, localidad, VRF y ocupación.
- Fabricantes, modelos, ficha completa y plantillas de puertos.
- Creación de modelos con imágenes opcionales.
- Persistencia local frontal/trasera vinculada al `device_type_id`.
- Reemplazo idempotente y fallback a imágenes antiguas de NetBox.
- Planes seguros, lista cerrada de capacidades y vista previa de cables.

## En progreso en `feature/rack-image-containment`

### Experiencia 3D del rack

- La opción 3D solo se selecciona dentro de `/racks/{id}`.
- Gabinete metálico con profundidad, rieles, ventilación y piso técnico.
- Perspectiva isométrica o frontal.
- Cara frontal o trasera.
- Escala **Ajustar** o **Detalle** para mejorar la lectura de equipos de 1U.
- Fotografías frontales y traseras con ajuste proporcional `contain`, centradas y sin zoom automático tanto en rack completo como en detalle ampliado y elevación 2D; conservan la ocupación física exacta en U y no reciben etiquetas superpuestas.
- Inspector lateral compartido entre 2D y 3D.
- Conflictos físicos destacados en rojo.

### Reemplazo de imágenes

- La galería indica de forma explícita **Agregar** o **Reemplazar**.
- Se puede sustituir una sola cara sin modificar la otra.
- La respuesta de medios usa revalidación para reflejar el cambio al recargar.
- Se muestran metadatos básicos de la imagen local.

### Reporte PDF del rack

- Nueva ruta `GET /racks/{rack_id}/report.pdf`.
- Requiere permiso `racks.view`.
- Incluye resumen físico, elevación y listado paginado.
- Registra equipos posicionados, de 0U y sin posición válida.
- Incluye nombre, modelo, posición, altura, cara, estado, serial, activo y existencia de fotografía.
- Se genera en memoria y se descarga como archivo; no queda persistido.

## Validaciones automatizadas de la rama

- compilación Python;
- grafo Alembic con una sola cabeza;
- suite aislada sobre una base temporal;
- importación de la aplicación;
- análisis de plantillas y scripts;
- creación del PDF y estructura `%PDF`/`xref`;
- descarga autenticada del reporte;
- cálculo de alturas, caras, equipos de 0U y conflictos;
- persistencia y sustitución de imágenes locales.

## Requiere verificación en desarrollo

- desplegar la rama únicamente en el puerto 8101;
- abrir un rack de 42U en vista 3D;
- comparar **Ajustar** y **Detalle**;
- verificar equipos de 1U, 2U y chasis altos;
- alternar frente y parte trasera;
- reemplazar una imagen y confirmar el cambio inmediato;
- revisar el inspector lateral en 2D y 3D;
- descargar el reporte PDF y verificar todas las páginas;
- confirmar que producción no cambió.

## Riesgos y deuda

- Las imágenes aumentan el tamaño de la base local; el respaldo y el espacio libre deben supervisarse.
- SQLite es adecuado para el tamaño inicial, pero debe reevaluarse antes de varios workers o miles de modelos.
- El `device_type_id` es una referencia externa: una futura eliminación de modelos necesitará limpieza controlada de imágenes huérfanas.
- La creación del modelo en NetBox y el guardado local de imágenes no forman una única transacción.
- El PDF representa el rack mediante bloques imprimibles y no incrusta todas las fotografías del navegador.
- El rollback de código no revierte migraciones ni restaura la base.
- Aún faltan editores propios para bahías de módulos, energía, consola y patch panels.
- El asistente conversacional todavía no tiene interfaz ni ejecutor habilitado.

## Próximo objetivo

Validar el rack estilo datacenter y el reporte PDF en desarrollo. Después se decidirá si esta iteración se fusiona a `develop` y, tras una revisión adicional, se promueve a producción.

## Reglas de mantenimiento

Actualizar este documento en todo PR que modifique funcionalidad, arquitectura, seguridad, despliegue, dependencias, pruebas, riesgos o prioridades. Estados permitidos: **Completado**, **En progreso**, **Planificado**, **Bloqueado**, **Diferido** y **Requiere verificación**.
