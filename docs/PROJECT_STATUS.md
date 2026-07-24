# Estado del proyecto: NetDoc

- **Propósito:** interfaz operativa para consultar, crear y visualizar inventario de red cuyo origen oficial es NetBox.
- **Estado general:** En progreso.
- **Última actualización:** 2026-07-24.
- **Versión documental:** 1.8.
- **Versión de aplicación de la rama:** 0.10.0.
- **Responsable / repositorio:** Luis Emilio García Pichardo / `tito9903-byte/netdoc`.
- **Ramas:** producción `main`; desarrollo `develop`; trabajo actual `feature/documentation-workflows-ui`.

## Resumen ejecutivo

`develop` contiene la versión 0.9.0 validada en el puerto 8101 con autenticación multiusuario, roles, auditoría, perfil, búsqueda global, Sistema y Alembic. El PR #4 permanece como borrador e inicia la siguiente etapa: convertir NetDoc en una capa de documentación más rápida que la interfaz general de NetBox, con flujos dirigidos para IPAM, modelos de equipos, interfaces en lote, racks y altas físicas.

La rama 0.10.0 incorpora una primera revisión visual basada en las pantallas reales suministradas por el propietario, además de nuevas funciones operativas. No ha sido fusionada ni desplegada en el servidor.

## Entornos y servicios

| Entorno | Estado conocido | Ruta | Rama | Servicio | Puerto | Sesión |
|---|---|---|---|---|---:|---|
| Producción | Verificado manualmente por el propietario | `/opt/netdoc-prod` | `main` | `netdoc-prod` | 8100 | independiente |
| Desarrollo | Verificado manualmente por el propietario con versión 0.9.0 | `/opt/netdoc-dev` | `develop` | `netdoc-dev` | 8101 | `netdoc_dev_session` |

Servidor dedicado: `192.168.10.93`; NetBox: `https://192.168.10.95`, versión documentada 4.4.2. Desarrollo debe conservar `NETBOX_WRITE_ENABLED=false`. El respaldo `/opt/netbox-documental` no es producción activa.

## Arquitectura vigente

- FastAPI, Jinja2, HTTPX, Pydantic Settings, SessionMiddleware y Uvicorn.
- NetBox conserva dispositivos, tipos de dispositivo, componentes, racks, sitios, cables, prefijos, direcciones y demás inventario.
- SQLAlchemy conserva únicamente usuarios, roles, permisos y auditoría de NetDoc.
- Alembic mantiene el historial versionado del esquema local; la cabeza actual es `20260724_0001`.
- SQLite es el valor inicial de `DATABASE_URL`; cada entorno debe tener su propia base.
- `PermissionMiddleware` recarga la identidad activa y los permisos antes de cada solicitud protegida.
- Las escrituras nuevas exigen autenticación, permiso, CSRF y `NETBOX_WRITE_ENABLED=true`.
- Los nuevos servicios de IPAM, modelos y racks consumen la API REST de NetBox y no duplican inventario en la base local.

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
- Foco visible, objetivos táctiles mayores, estados activos y cierre accesible del menú móvil.
- Dashboard convertido en punto de inicio para los principales procesos de documentación.
- Búsqueda global con accesos directos a dispositivos, IPAM, racks y modelos.
- Jerarquía visual común para formularios, filtros, avisos, estados y tablas.
- Ajustes responsivos para pantallas medianas y móviles.
- Botones administrativos alineados y tablas con estados de interacción más claros.

### Direccionamiento IP

- Nueva pantalla `/ipam` para prefijos y pools.
- Filtros por texto, familia IP, estado y rol.
- Localidad o alcance, VRF, rol y estado visibles por prefijo.
- Consulta de direcciones disponibles por pool mediante la API de NetBox.
- Cálculo de capacidad, usadas, disponibles y porcentaje de ocupación.
- Clasificación visual de pools saludables, en advertencia, críticos y llenos.
- API interna de solo lectura `/api/ipam/pools`.

### Modelos y plantillas

- Nueva pantalla `/device-types` para consultar modelos y componentes.
- Creación guiada de tipos de dispositivo cuando la escritura está habilitada.
- Generación de hasta 256 plantillas de interfaz en una operación.
- Patrones como `GigabitEthernet0/{n}` y `Gi1/0/{n:02}`.
- Vista previa interactiva antes de enviar el lote.
- Descubrimiento de tipos de interfaz mediante `OPTIONS` con opciones seguras de respaldo.
- Auditoría de creación de modelos y plantillas.
- El alta de equipos enlaza directamente al catálogo de modelos.

### Racks y altas físicas

- Corrección del ancho de rack cuando NetBox devuelve una opción estructurada.
- Ocupación desconocida mostrada como pendiente en lugar de `0.0%` engañoso.
- Alta de equipos orientada a modelo, sitio, rack, posición U y cara.
- Nuevo formulario `/racks/actions/new` para crear racks con sitio, ubicación, capacidad, ancho, unidad inicial, estado, rol e identificadores.
- Filtrado de ubicaciones por sitio.
- Acciones directas desde el inventario de racks.

### Conexiones

- Aviso explícito cuando desarrollo está en solo lectura.
- Botón de creación bloqueado visual y funcionalmente sin escritura.
- Presentación defensiva de extremos, tipos, estados y unidades devueltos por NetBox.

## Validaciones de la rama

Ejecutadas fuera del servidor:

- Compilación de Python: correcta.
- Grafo Alembic: correcto.
- Suite automatizada completa: correcta.
- Siete pruebas nuevas para patrones de interfaces, slug y capacidad/localidad IPAM: correctas.
- Importación de la aplicación: correcta.
- Análisis de todas las plantillas Jinja2: correcto.
- Sintaxis de scripts de despliegue: correcta.
- GitHub Actions `NetDoc CI` completó todas las etapas correctamente en el último conjunto funcional validado.

Pendiente:

- Validar los endpoints nuevos con NetBox 4.4.2 y datos reales.
- Revisar rendimiento cuando existan muchos pools, pues la disponibilidad se consulta por pool con concurrencia limitada.
- Probar creación real de modelo, interfaces y rack en un entorno autorizado para escritura.
- Revisar visualmente todas las pantallas en el puerto 8101.
- Confirmar que los campos opcionales de racks coinciden con las personalizaciones del NetBox instalado.

## Riesgos y deuda

- La rama reutiliza permisos existentes (`search.view`, `devices.view` y `devices.create`); se evaluarán permisos específicos de IPAM, modelos y racks después de validar el flujo.
- La consulta de disponibilidad IPAM realiza una solicitud adicional por pool; puede requerir caché o resumen progresivo con inventarios muy grandes.
- La creación masiva de interfaces depende de la validación atómica de NetBox; cualquier error debe presentarse de manera clara antes de reintentar.
- La ocupación completa de todos los racks no se calcula todavía en el listado para evitar una consulta costosa por cada rack.
- SQLite debe reevaluarse antes de varios workers o mayor concurrencia.
- El rollback de código no revierte migraciones ni restaura automáticamente la base local.
- El token de NetBox previamente expuesto debe rotarse y reducirse a mínimo privilegio.
- Falta definir retención, respaldo y eliminación segura de eventos de auditoría.

## Próximo objetivo

**En progreso:** terminar la validación del PR #4, desplegarlo únicamente en desarrollo después de autorización, revisar las pantallas con datos reales y corregir incompatibilidades antes de cualquier fusión a `develop`. Las siguientes iteraciones cubrirán reservas y disponibilidad de unidades U, creación acelerada de otros componentes de modelos, VLAN/prefijos guiados, circuitos y documentación física avanzada.

## Reglas de mantenimiento

Actualizar este documento en todo PR que modifique funcionalidad, arquitectura, seguridad, despliegues, dependencias, pruebas, riesgos o prioridades. Estados permitidos: **Completado**, **En progreso**, **Planificado**, **Bloqueado**, **Diferido** y **Requiere verificación**.
