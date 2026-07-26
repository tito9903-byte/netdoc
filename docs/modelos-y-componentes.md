# Modelos, puertos y componentes en NetDoc

## Objetivo

La biblioteca de modelos es la fuente única de documentación reutilizable para los equipos que NetBox crea después. Un modelo reúne:

- fabricante, modelo, part number, slug, altura y profundidad;
- campos avanzados publicados por la API de la versión conectada de NetBox;
- fotografía frontal y trasera utilizada por la vista 3D y los reportes de rack;
- interfaces y puertos;
- alimentación, consola, bahías y elementos internos;
- dispositivos creados a partir del modelo.

La antigua entrada independiente **Plantillas de puertos** se conserva únicamente como ruta de compatibilidad. El flujo normal se realiza dentro de **Modelos de equipos**.

## Crear un modelo

1. Abrir **Documentación → Modelos de equipos**.
2. Pulsar **Crear modelo**.
3. Seleccionar fabricante y completar la identificación física.
4. Revisar los campos avanzados obtenidos mediante `OPTIONS /api/dcim/device-types/`.
5. Cargar, cuando estén disponibles, la fotografía frontal y trasera.
6. Guardar el modelo.

NetDoc crea la ficha en NetBox, guarda las imágenes en su base local y registra el resultado en auditoría.

## Imágenes para racks

Para obtener una representación clara:

- usar vista frontal o trasera recta, sin perspectiva;
- preferir PNG con transparencia real;
- recortar el lienzo cerca de los límites físicos del equipo;
- evitar bordes blancos, sombras grandes y espacios vacíos;
- verificar que la altura U configurada corresponda al equipo real;
- conservar textos, puertos, logotipos y distribución física del modelo original.

Las imágenes no determinan la altura ocupada. La capacidad vertical se obtiene del campo `u_height` del modelo.

## Puertos y componentes

En la ficha del modelo, la sección **Puertos, interfaces y componentes** permite documentar:

1. interfaces de red;
2. puertos de consola;
3. puertos de servidor de consola;
4. entradas de energía;
5. salidas de energía;
6. puertos frontales;
7. puertos traseros;
8. bahías de módulos;
9. bahías de dispositivos;
10. elementos de inventario.

Los campos, tipos y opciones de cada formulario se consultan desde el endpoint `OPTIONS` correspondiente de NetBox. Esto evita mantener en NetDoc una lista incompleta de tipos de interfaz y permite adaptarse a nuevas versiones.

## Creación individual y por lotes

El campo **Nombre o patrón** acepta:

- un nombre literal cuando se crea un solo registro, por ejemplo `MGMT`;
- `{n}` para numeración sencilla, por ejemplo `GigabitEthernet0/{n}`;
- formatos de Python como `{n:02}`, por ejemplo `Gi1/0/{n:02}`.

El lote admite hasta 256 registros. NetBox valida todo el contenido antes de guardarlo.

## Relaciones entre componentes

Algunos componentes dependen de otros:

- un puerto frontal puede requerir un puerto trasero y una posición;
- una salida de energía puede asociarse a una entrada de energía;
- un elemento de inventario puede depender de otro elemento padre.

NetDoc consulta los componentes existentes del mismo modelo y los presenta como opciones, evitando introducir identificadores manualmente.

## Seguridad y trazabilidad

- Las escrituras requieren el permiso `devices.create`.
- Los formularios utilizan protección CSRF.
- La escritura puede bloquearse globalmente con el modo de solo lectura.
- Las altas y errores se registran en la auditoría de NetDoc.
- NetBox conserva su propio historial de cambios.

## Uso móvil

Los listados conservan desplazamiento horizontal cuando una tabla no cabe. Los formularios de creación se abren como ventana en escritorio y ocupan la pantalla completa en teléfonos. Los controles principales mantienen un área táctil adecuada.
