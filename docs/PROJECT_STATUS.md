# Estado del proyecto: NetDoc

- **Propósito:** interfaz operativa para consultar, crear y visualizar inventario de red cuyo origen oficial es NetBox.
- **Estado general:** En progreso.
- **Última actualización:** 2026-07-24.
- **Versión documental:** 1.9.
- **Versión de aplicación de la rama:** 0.10.0.
- **Responsable / repositorio:** Luis Emilio García Pichardo / `tito9903-byte/netdoc`.
- **Ramas:** producción `main`; desarrollo `develop`; trabajo actual `feature/documentation-workflows-ui`.

## Resumen ejecutivo

`develop` contiene la versión 0.9.0 con autenticación multiusuario, roles, auditoría, perfil, búsqueda global, Sistema y Alembic. El PR #4 permanece como borrador y convierte NetDoc en una capa de documentación más rápida que la interfaz general de NetBox, con flujos dirigidos para IPAM, modelos, imágenes, interfaces en lote, racks y altas físicas.

La rama 0.10.0 ha sido revisada iterativamente en el puerto 8101 con datos reales de NetBox 4.4.2. Cada nuevo commit debe desplegarse y comprobarse nuevamente antes de considerarse validado. No ha sido fusionada a `develop` ni promovida a producción.

## Entornos y servicios

| Entorno | Estado conocido | Ruta | Rama esperada | Servicio | Puerto | Sesión |
|---|---|---|---|---|---:|---|
| Producción | Verificado manualmente por el propietario | `/opt/netdoc-prod` | `main` | `netdoc-prod` | 8100 | independiente |
| Desarrollo | Usado para revisión manual del PR #4 | `/opt/netdoc-dev` | rama del PR durante revisión; `develop` después de fusionar | `netdoc-dev` | 8101 | `netdoc_dev_session` |

Servidor dedicado: `192.168.10.93`; NetBox: `https://192.168.10.95`, versión documentada 4.4.2. Desarrollo debe conservar `NETBOX_WRITE_ENABLED=false` durante las revisiones de lectura. El respaldo `/opt/netbox-documental` no es producción activa.

## Arquitectura vigente

- FastAPI, Jinja2, HTTPX, Pydantic Settings, SessionMiddleware y Uvicorn.
- NetBox conserva dispositivos, tipos de dispositivo, componentes, imágenes, racks, sitios, cables, prefijos, direcciones y demás inventario.
- SQLAlchemy conserva únicamente usuarios, roles, permisos y auditoría de NetDoc.
- Alembic mantiene el historial versionado del esquema local; la cabeza actual es `20260724_0001`.
- SQLite es el valor inicial de `DATABASE_URL`; cada entorno debe tener su propia base.
- `PermissionMiddleware` recarga la identidad activa y los permisos antes de cada solicitud protegida.
- Las escrituras nuevas exigen autenticación, permiso, CSRF y `NETBOX_WRITE_ENABLED=true`.
- Los servicios de IPAM, modelos, imágenes y racks consumen la API REST de NetBox y no duplican inventario en la base local.
- Las imágenes privadas de tipos de dispositivo se sirven al navegador mediante un proxy autenticado; el token de NetBox no se expone.

## Completado en `develop`

- Dashboard, dispositivos e interfaces, filtros y paginación.
- Creación guiada de equipos.
- Consulta y creación de conexiones y cables.
- Racks con listado, detalle, inspector y elevación 2D.
- Autenticación multiusuario, roles Administrador, Operador y Consulta, roles personalizados y 11 permisos.
- Administración de usuarios, perfil de autoservicio y cambio de contraseña.
- Auditoría con filtros y exportación CSV.
- Protección temporal contra intentos repetidos de login.
- Búsqueda global y módulo Sistema de solo lectura.
- Migración inicial Alembic y adopción controlada de bases heredadas completas.
- Despliegue separado y validado para desarrollo y producción.

## En progreso en `feature/documentation-workflows-ui`

### Experiencia visual y navegación

- Navegación agrupada por General, Documentación, Acciones rápidas y Administración.
- Modelos de equipos y plantillas de puertos separados en procesos independientes.
- La Topología 3D deja de ocupar una opción independiente: se selecciona dentro del detalle del rack mediante **Vista 2D / Vista 3D**.
- Foco visible, objetivos táctiles mayores, estados activos y cierre accesible del menú móvil.
- Dashboard convertido en punto de inicio para los principales procesos de documentación.
- Búsqueda global con accesos directos a dispositivos, IPAM, racks y modelos.
- Jerarquía visual común para formularios, filtros, avisos, estados y tablas.

### Direccionamiento IP

- Pantalla `/ipam` para prefijos y pools.
- Filtros por texto, familia, estado, rol, localidad y condición de disponibilidad.
- Localidad o alcance, VRF, rol y estado visibles por prefijo.
- Cálculo de capacidad y disponibilidad desde direcciones, rangos y prefijos hijos documentados en la misma VRF.
- Clasificación visual de pools saludables, en advertencia, críticos y llenos.
- Paginación, orden y cantidades IPv6 compactas.
- API interna de solo lectura `/api/ipam/pools`.

### Modelos, plantillas e imágenes

- Pantalla `/device-types` dedicada al catálogo de modelos y componentes.
- Pantalla `/device-types/new` dedicada a crear el modelo.
- Pantalla `/interface-templates` dedicada a plantillas de puertos.
- Generación de hasta 256 plantillas en una operación mediante patrones como `GigabitEthernet0/{n}` y `Gi1/0/{n:02}`.
- Vista previa interactiva antes de enviar el lote.
- El formulario de creación del modelo admite imagen frontal y trasera en la misma operación.
- Validación previa de JPG, PNG, WEBP o GIF, con máximo de 5 MB por imagen.
- Si la carga de imágenes falla después de crear el modelo, el modelo se conserva y el usuario puede repetir solo la carga desde la galería.
- Galería posterior `/device-types/{id}/images` para sustituir las imágenes.
- Auditoría separada para creación de modelo y actualización de imágenes.

### Racks y altas físicas

- Ocupación calculada con la posición y el `u_height` real del modelo.
- Soporte para equipos de 0U, 0.5U y alturas superiores.
- Respeto de cara frontal, cara trasera y profundidad completa.
- Detección de superposiciones físicas.
- Selector **Vista 2D / Vista 3D** dentro de `/racks/{id}`.
- La vista 2D y la vista 3D reutilizan la imagen frontal o trasera del modelo.
- Alta de equipos orientada a modelo, sitio, rack, posición U y cara.
- Formulario `/racks/actions/new` para crear racks con sitio, ubicación, capacidad, ancho, unidad inicial, estado, rol e identificadores.
- Filtrado de ubicaciones por sitio y acciones directas desde el inventario de racks.
- `/topology` se conserva únicamente como redirección de compatibilidad hacia Racks.

### Conexiones

- Aviso explícito cuando desarrollo está en solo lectura.
- Botón de creación bloqueado visual y funcionalmente sin escritura.
- Presentación descriptiva de equipo e interfaz en cada extremo.
- Tipos, estados y unidades traducidos y presentados defensivamente.

## Validaciones de la rama

Automatizadas:

- Compilación de Python.
- Grafo Alembic.
- Suite aislada sobre SQLite temporal.
- Importación de la aplicación.
- Análisis de plantillas Jinja2.
- Sintaxis de scripts de despliegue.
- Pruebas de alturas fraccionarias, 0U, profundidad completa, conflictos, proxy de imágenes, agrupación física, formularios separados y ruta combinada de modelo e imágenes.
- GitHub Actions `NetDoc CI` completado correctamente para el último commit funcional antes de cada despliegue manual.

Pendiente o requiere verificación:

- Desplegar el último commit únicamente en desarrollo y revisar el selector 2D/3D del rack.
- Verificar con escritura autorizada la creación real de un modelo junto con imagen frontal y trasera.
- Confirmar que NetBox 4.4.2 acepta el `PATCH multipart` para ambos campos de imagen.
- Revisar el ajuste visual de fotografías reales con distintas proporciones y fondos.
- Confirmar que los campos opcionales de racks coinciden con las personalizaciones del NetBox instalado.
- Agregar conexiones físicas o lógicas sobre la representación 3D en una etapa posterior.

## Riesgos y deuda

- La rama reutiliza permisos existentes (`search.view`, `devices.view`, `devices.create` y `racks.view`); se evaluarán permisos específicos después de validar los flujos.
- La creación masiva de interfaces depende de la validación de NetBox; cualquier error debe presentarse claramente antes de reintentar.
- La creación del modelo y la carga de imágenes no son una transacción única de NetBox. Un fallo de imagen puede dejar el modelo correctamente creado y requiere reintento desde la galería.
- Fotografías con perspectiva, márgenes o fondos no transparentes pueden verse deformadas al ajustarse a la altura física del rack.
- SQLite debe reevaluarse antes de varios workers o mayor concurrencia.
- El rollback de código no revierte migraciones ni restaura automáticamente la base local.
- El token de NetBox previamente expuesto debe rotarse y reducirse a mínimo privilegio.
- Falta definir retención, respaldo y eliminación segura de eventos de auditoría.

## Próximo objetivo

**En progreso:** desplegar y revisar el último commit del PR #4 únicamente en desarrollo. Validar creación de modelo con imágenes, vistas 2D/3D por rack, caras frontal/trasera, altura U y superposiciones antes de cualquier fusión a `develop`. Las siguientes iteraciones cubrirán plantillas para otros componentes, VLAN/prefijos guiados, circuitos y relaciones físicas entre equipos.

## Reglas de mantenimiento

Actualizar este documento en todo PR que modifique funcionalidad, arquitectura, seguridad, despliegues, dependencias, pruebas, riesgos o prioridades. Estados permitidos: **Completado**, **En progreso**, **Planificado**, **Bloqueado**, **Diferido** y **Requiere verificación**.