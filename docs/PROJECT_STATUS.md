# Estado del proyecto: NetDoc

- **Propósito:** interfaz operativa para consultar, crear y visualizar inventario de red cuyo origen oficial es NetBox.
- **Estado general:** En progreso.
- **Última actualización:** 2026-07-24.
- **Versión documental:** 2.0.
- **Versión de aplicación de la rama:** 0.10.0.
- **Responsable / repositorio:** Luis Emilio García Pichardo / `tito9903-byte/netdoc`.
- **Ramas:** producción `main`; desarrollo `develop`; trabajo actual `feature/documentation-workflows-ui`.

## Resumen ejecutivo

`develop` contiene la versión 0.9.0 con autenticación multiusuario, roles, auditoría, perfil, búsqueda global, Sistema y Alembic. El PR #4 permanece como borrador y convierte NetDoc en una capa de documentación más rápida que la interfaz general de NetBox, con flujos dirigidos para IPAM, modelos, imágenes, interfaces en lote, racks y altas físicas.

La rama 0.10.0 ha sido revisada iterativamente en el puerto 8101 con datos reales de NetBox 4.4.2. Los últimos commits añaden el fundamento de planes seguros y del futuro asistente, pero todavía no han sido desplegados manualmente en el servidor. No se ha fusionado a `develop` ni promovido a producción.

## Entornos y servicios

| Entorno | Estado conocido | Ruta | Rama esperada | Servicio | Puerto | Sesión |
|---|---|---|---|---|---:|---|
| Producción | Verificado manualmente por el propietario | `/opt/netdoc-prod` | `main` | `netdoc-prod` | 8100 | independiente |
| Desarrollo | Usado para revisión manual del PR #4 | `/opt/netdoc-dev` | rama del PR durante revisión; `develop` después de fusionar | `netdoc-dev` | 8101 | `netdoc_dev_session` |

Servidor dedicado: `192.168.10.93`; NetBox: `https://192.168.10.95`, versión documentada 4.4.2. Desarrollo debe conservar `NETBOX_WRITE_ENABLED=false` durante las revisiones iniciales. El respaldo `/opt/netbox-documental` no es producción activa.

## Arquitectura vigente

- FastAPI, Jinja2, HTTPX, Pydantic Settings, SessionMiddleware y Uvicorn.
- NetBox conserva dispositivos, tipos, componentes, imágenes, racks, sitios, cables, IPAM y demás inventario.
- SQLAlchemy conserva únicamente usuarios, roles, permisos y auditoría de NetDoc.
- Alembic mantiene el historial versionado del esquema local; la cabeza actual es `20260724_0001`.
- SQLite es el valor inicial de `DATABASE_URL`; cada entorno debe tener su propia base.
- `PermissionMiddleware` recarga identidad y permisos antes de cada solicitud protegida.
- Las escrituras exigen autenticación, permiso, CSRF y `NETBOX_WRITE_ENABLED=true`.
- Los servicios consumen la API REST de NetBox y no duplican inventario en la base local.
- Las imágenes privadas se sirven mediante proxy autenticado; el token no se expone.
- Los cambios futuros de formularios e IA convergen en un `ChangePlan` determinista.
- La lista cerrada de capacidades impide que un cliente o modelo invente rutas REST.
- El esquema de la instalación se descubre mediante `OPTIONS` antes de habilitar una nueva escritura.

## Completado en `develop`

- Dashboard, dispositivos e interfaces, filtros y paginación.
- Creación guiada de equipos.
- Consulta y creación de conexiones y cables.
- Racks con listado, detalle, inspector y elevación 2D.
- Autenticación multiusuario, roles iniciales y roles personalizados.
- Administración de usuarios, perfil y cambio de contraseña.
- Auditoría con filtros y exportación CSV.
- Protección temporal contra intentos repetidos de login.
- Búsqueda global y módulo Sistema de solo lectura.
- Migración inicial Alembic y adopción controlada de bases heredadas completas.
- Despliegue separado y validado para desarrollo y producción.

## En progreso en `feature/documentation-workflows-ui`

### Experiencia visual y navegación

- Navegación agrupada por General, Documentación, Acciones rápidas y Administración.
- Modelos y plantillas de puertos separados en procesos independientes.
- Topología 3D seleccionable dentro del detalle del rack.
- Dashboard como punto de inicio de los principales procesos.
- Jerarquía visual común para formularios, filtros, avisos, estados y tablas.
- Pendiente reorganizar hardware en apartados de fabricantes, modelos y componentes con creación y edición desde cada ficha.

### Direccionamiento IP

- Pantalla `/ipam` para prefijos y pools.
- Filtros por texto, familia, estado, rol, localidad y disponibilidad.
- Localidad, VRF, rol y estado visibles por prefijo.
- Cálculo desde direcciones, rangos y prefijos hijos documentados en la misma VRF.
- Clasificación visual, paginación, orden y cantidades IPv6 compactas.
- API interna de solo lectura `/api/ipam/pools`.

### Modelos, plantillas e imágenes

- Catálogo `/device-types`, alta `/device-types/new` y plantillas `/interface-templates`.
- Generación de hasta 256 plantillas mediante patrones con vista previa.
- Imagen frontal y trasera opcionales al crear el modelo.
- Validación de JPG, PNG, WEBP o GIF, máximo 5 MB.
- Galería `/device-types/{id}/images` para sustituir imágenes.
- Auditoría separada para creación del modelo y actualización de imágenes.
- Pendiente: ficha individual con pestañas, edición, fabricantes y otros componentes.

### Racks y altas físicas

- Ocupación con posición y `u_height` real.
- Equipos de 0U, 0.5U y alturas superiores.
- Cara frontal, trasera, profundidad completa y superposiciones.
- Selector Vista 2D / Vista 3D en `/racks/{id}`.
- Fotografías reutilizadas en ambas vistas.
- Alta guiada de rack y colocación física del equipo.
- `/topology` reservado como redirección de compatibilidad.

### Conexiones

- Presentación descriptiva de equipo e interfaz.
- Tipos, estados y unidades traducidos defensivamente.
- Creación actual protegida por sesión, permisos, CSRF y modo de escritura.
- Nuevo planificador determinista que rechaza extremos ocupados, iguales o inválidos.
- Nueva API `POST /api/change-plans/cable` que consulta los extremos y devuelve una vista previa; no escribe.

### Escrituras seguras y futuro asistente

- `ChangePlan` con pasos, dependencias, advertencias, huella y frase de confirmación.
- Redacción recursiva de secretos para UI, logs y auditoría.
- Rechazo de `DELETE` en planes automáticos.
- Lista cerrada de capacidades para fabricantes, modelos, plantillas, racks, dispositivos, cables, IPAM y circuitos.
- Solo la creación de cable está marcada inicialmente como candidata a ejecución asistida; las demás operaciones pueden prepararse, pero no ejecutarse por IA.
- Descubrimiento de campos, obligatoriedad y opciones mediante `OPTIONS`.
- Validación dinámica de payload contra la versión y plugins instalados.
- Documentación de la arquitectura conversacional y mapa completo de módulos.
- Todavía no existe interfaz de chat ni ejecutor automático.

## Validaciones de la rama

Automatizadas:

- compilación de Python;
- grafo Alembic;
- suite aislada sobre SQLite temporal;
- importación de la aplicación;
- análisis de plantillas Jinja2;
- sintaxis de scripts;
- alturas fraccionarias, 0U, profundidad completa, conflictos e imágenes;
- separación de formularios y ruta combinada de modelo e imágenes;
- planes, huellas, redacción, lista cerrada y confirmación;
- planificador y vista previa de cable;
- análisis de esquemas `OPTIONS` y validación de campos/opciones;
- GitHub Actions correcto para el último commit verificado.

Pendiente o requiere verificación:

- desplegar el último commit únicamente en desarrollo;
- revisar fabricantes/modelos/componentes con la reorganización pendiente;
- verificar creación real de un modelo con imágenes en un entorno autorizado;
- comprobar el `PATCH multipart` de NetBox 4.4.2;
- revisar fotografías reales con diferentes proporciones;
- probar la API de vista previa de cable contra interfaces reales;
- comparar opciones de cable con `OPTIONS` de la instalación;
- diseñar el ejecutor confirmado sin habilitarlo todavía;
- no fusionar ni tocar producción hasta aprobación explícita.

## Riesgos y deuda

- La rama reutiliza permisos amplios existentes; se requieren permisos separados por dominio antes del asistente.
- El token técnico debe rotarse y restringirse por objetos y acciones.
- La creación del modelo y las imágenes no es una única transacción; un fallo puede requerir reintento.
- Los flujos compuestos necesitan estados parciales y compensaciones explícitas.
- El esquema `OPTIONS` de plugins puede diferir y debe tratarse defensivamente.
- Una fotografía no sustituye la altura correcta del modelo.
- SQLite debe reevaluarse antes de varios workers.
- El rollback de código no revierte migraciones ni restaura automáticamente la base local.
- Falta definir retención y eliminación segura de auditoría.
- El asistente futuro debe resistir prompt injection, ambigüedad y solicitudes fuera de capacidad.

## Próximo objetivo

**En progreso:** reorganizar fabricantes, modelos, imágenes y plantillas como fichas administrables; desplegar y revisar el último PR #4 en desarrollo; integrar la vista previa segura en el flujo de conexiones; y preparar resolutores exactos de objetos. Después se construirá un asistente de solo lectura que guíe al usuario y produzca planes sin ejecutar. La primera escritura conversacional prevista será la creación confirmada de un cable.

## Reglas de mantenimiento

Actualizar este documento en todo PR que modifique funcionalidad, arquitectura, seguridad, despliegue, dependencias, pruebas, riesgos o prioridades. Estados permitidos: **Completado**, **En progreso**, **Planificado**, **Bloqueado**, **Diferido** y **Requiere verificación**.
