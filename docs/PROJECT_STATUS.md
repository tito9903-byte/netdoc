# Estado del proyecto: NetDoc

- **Propósito:** interfaz operativa para consultar, crear y visualizar inventario de red cuyo origen oficial es NetBox.
- **Estado general:** En progreso.
- **Última actualización:** 2026-07-25.
- **Versión documental:** 2.2.
- **Versión de aplicación de la rama:** 0.10.1.
- **Responsable / repositorio:** Luis Emilio García Pichardo / `tito9903-byte/netdoc`.
- **Ramas:** producción `main`; integración `develop`; trabajo actual `feature/local-device-type-images`.

## Resumen ejecutivo

La versión `0.10.0` fue promovida a `main` y reúne autenticación, roles, auditoría, búsqueda, Sistema, IPAM, fabricantes, modelos, plantillas, conexiones, racks 2D/3D y la base segura para el futuro asistente.

La rama `feature/local-device-type-images` prepara `0.10.1` para resolver una limitación detectada al subir imágenes mediante NetBox 4.4.2: el proceso de NetBox no podía escribir en su directorio multimedia. La solución no cambia permisos del servidor NetBox. NetDoc guarda las nuevas imágenes frontal y trasera en su propia base, vinculadas al `device_type_id` real de NetBox.

## Entornos y servicios

| Entorno | Ruta | Rama esperada | Servicio | Puerto | Base local |
|---|---|---|---|---:|---|
| Producción | `/opt/netdoc-prod` | `main` | `netdoc-prod` | 8100 | independiente |
| Desarrollo | `/opt/netdoc-dev` | rama en revisión o `develop` | `netdoc-dev` | 8101 | independiente |

Servidor dedicado: `192.168.10.93`. NetBox: `https://192.168.10.95`, versión documentada 4.4.2.

## Arquitectura vigente

- FastAPI, Jinja2, HTTPX, Pydantic Settings, SessionMiddleware y Uvicorn.
- NetBox conserva dispositivos, tipos, componentes, racks, sitios, cables, IPAM y demás inventario.
- SQLAlchemy conserva usuarios, roles, permisos, auditoría e imágenes de modelos propias de NetDoc.
- Alembic mantiene el esquema local; la cabeza de esta rama es `20260725_0002`.
- SQLite es el valor inicial de `DATABASE_URL`; cada entorno usa su propia base.
- Las escrituras hacia NetBox exigen autenticación, permiso, CSRF y `NETBOX_WRITE_ENABLED=true`.
- La escritura local de imágenes exige autenticación, permiso `devices.create` y CSRF, pero no modifica NetBox.
- Las imágenes se entregan mediante una ruta autenticada; el token de NetBox no se expone.
- Los cambios futuros de formularios e IA convergen en un `ChangePlan` determinista.

## Funcionalidades disponibles en 0.10.0

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
- Planes seguros, lista cerrada de capacidades y vista previa de cables.

## En progreso en `feature/local-device-type-images`

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

## Validaciones automatizadas de la rama

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

## Requiere verificación en desarrollo

- desplegar la rama únicamente en el puerto 8101;
- confirmar `alembic current` y `alembic heads` en `20260725_0002`;
- cargar una imagen en un modelo existente;
- confirmar la etiqueta **Guardada en NetDoc**;
- revisar la misma imagen en catálogo, ficha, rack 2D y rack 3D;
- sustituirla y comprobar el cambio de `ETag`;
- revisar el evento de auditoría;
- confirmar que NetBox no recibió un `PATCH` de imagen.

## Riesgos y deuda

- Las imágenes aumentan el tamaño de la base local; el respaldo y el espacio libre deben supervisarse.
- SQLite es adecuado para el tamaño inicial, pero debe reevaluarse antes de varios workers o miles de modelos.
- El `device_type_id` es una referencia externa: una futura eliminación de modelos necesitará limpieza controlada de imágenes huérfanas.
- La creación del modelo en NetBox y el guardado local de imágenes no forman una única transacción.
- El rollback de código no revierte migraciones ni restaura la base.
- Aún faltan editores propios para bahías de módulos, energía, consola y patch panels.
- El asistente conversacional todavía no tiene interfaz ni ejecutor habilitado.

## Próximo objetivo

Validar `0.10.1` en desarrollo. Después de confirmar migración, carga y visualización en racks, abrir la promoción `develop → main`. La siguiente etapa funcional continuará con componentes de modelos y conexiones físicas guiadas.

## Reglas de mantenimiento

Actualizar este documento en todo PR que modifique funcionalidad, arquitectura, seguridad, despliegue, dependencias, pruebas, riesgos o prioridades. Estados permitidos: **Completado**, **En progreso**, **Planificado**, **Bloqueado**, **Diferido** y **Requiere verificación**.
