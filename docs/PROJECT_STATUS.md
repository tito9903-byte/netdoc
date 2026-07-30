# Estado del proyecto: NetDoc

- **Propósito:** interfaz operativa para consultar, crear y visualizar inventario de red cuyo origen oficial es NetBox.
- **Estado general:** En progreso.
- **Última actualización:** 2026-07-30.
- **Versión documental:** 2.8.
- **Versión de aplicación de la rama:** 0.10.1.
- **Responsable / repositorio:** Luis Emilio García Pichardo / `tito9903-byte/netdoc`.
- **Ramas:** producción `main`; integración `develop`; documentación actual
  `docs/netdoc-master`.

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

## Entornos y servicios

| Entorno | Ruta | Rama esperada | Servicio | Puerto | Base local |
|---|---|---|---|---:|---|
| Producción | `/opt/netdoc-prod` | `main` | `netdoc-prod` | 8100 | independiente |
| Desarrollo | `/opt/netdoc-dev` | rama en revisión o `develop` | `netdoc-dev` | 8101 | independiente |

Servidor dedicado: `192.168.10.93`. NetBox: `https://192.168.10.95`, versión documentada 4.4.2.

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
- Fabricantes, modelos, ficha completa y plantillas de puertos.
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

## Riesgos y deuda

- Las imágenes aumentan el tamaño de la base local; el respaldo y el espacio libre deben supervisarse.
- SQLite es adecuado para el tamaño inicial, pero debe reevaluarse antes de varios workers o miles de modelos.
- El `device_type_id` es una referencia externa: una futura eliminación de modelos necesitará limpieza controlada de imágenes huérfanas.
- La creación del modelo en NetBox y el guardado local de imágenes no forman una única transacción.
- El rollback de código no revierte migraciones ni restaura la base.
- Aún faltan editores propios para bahías de módulos, energía, consola y patch panels.
- El asistente conversacional todavía no tiene interfaz ni ejecutor habilitado.

## Próximo objetivo

Completar la revisión funcional de Sites. La imagen representativa del site
queda diferida hasta definir almacenamiento, respaldo y asociación sin duplicar
el inventario oficial.

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
