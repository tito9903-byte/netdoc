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

La navegación superior de la ficha muestra un contador junto a **Puertos y componentes**. El contador incluye interfaces, consola, energía y canales de paneles de parcheo. Cuando un panel tiene puertos frontales y traseros relacionados uno a uno, NetDoc utiliza la mayor cantidad de ambas caras para no contar dos veces el mismo canal físico. Las bahías y los elementos de inventario permanecen disponibles en la sección, pero no se suman como puertos.

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

## Crear dispositivos

El botón **Crear dispositivo** abre un formulario guiado en una ventana. El alta exige nombre, sitio, modelo y rol; opcionalmente permite documentar rack, posición, cara y número de serie.

La protección del formulario utiliza un token HMAC firmado con el secreto del servidor y la identidad autenticada. El token no se agrega dinámicamente a la cookie de sesión, evitando que las cargas paralelas de la página y la ventana modal lo sobrescriban. Si la validación falla, NetDoc vuelve a presentar el formulario con un mensaje comprensible y conserva los datos introducidos; nunca debe mostrar el JSON crudo de una excepción de seguridad.

## IP e interfaz principal del dispositivo

La ficha de cada dispositivo incluye la acción **Configurar** junto a **IP principal**. La ventana consulta únicamente las direcciones que NetBox tiene asignadas a las interfaces de ese equipo y muestra cada opción en el formato:

`dirección/prefijo — interfaz`

Se pueden definir por separado:

- `primary_ip4`, para IPv4;
- `primary_ip6`, para IPv6.

La interfaz principal no se selecciona de forma independiente: queda determinada por la interfaz a la que está asociada la IP elegida. Esto evita documentar una dirección y un puerto que no correspondan entre sí.

En los listados y racks, NetDoc muestra primero la IPv4 principal. Si el dispositivo no tiene una IPv4 principal, utiliza la IPv6 principal. Cuando ninguna está definida, muestra **Sin asignar**.

## Espacio de trabajo del rack

En pantallas de escritorio, el detalle del rack se organiza como un espacio de trabajo de dos columnas:

- a la izquierda permanece la vista 3D con proporciones fijas del gabinete;
- a la derecha se presentan el resumen físico, el inspector del equipo seleccionado y el inventario operativo;
- la vista 3D permanece visible mientras se revisa el inventario cuando hay espacio suficiente;
- las métricas superiores incluyen altura, unidades ocupadas, unidades libres, cantidad de equipos y utilización.

La información física se presenta de forma compacta para evitar una columna excesivamente larga. Los equipos de 0U y los equipos sin posición válida se mantienen disponibles en secciones desplegables.

## Inventario dentro del rack

El inventario presenta los dispositivos asociados con:

- nombre del dispositivo;
- modelo;
- posición U y cara;
- número de serie;
- IP principal;
- estado;
- acceso directo a la ficha del dispositivo.

La tabla permite buscar por nombre, modelo, dirección IP, número de serie, posición o estado. Su encabezado permanece visible durante el desplazamiento interno. Los equipos sin posición válida o de 0U también forman parte del inventario completo y la IP utiliza la selección principal configurada en el dispositivo.

## Seguridad y trazabilidad

- Las escrituras requieren el permiso `devices.create`.
- Los formularios utilizan protección CSRF firmada.
- La escritura puede bloquearse globalmente con el modo de solo lectura.
- Las altas, cambios de IP principal y errores se registran en la auditoría de NetDoc.
- NetBox conserva su propio historial de cambios mediante `changelog_message`.

## Uso móvil

Los formularios de creación ocupan la pantalla completa en teléfonos y mantienen controles táctiles adecuados. En el detalle de un rack, la vista 3D, la información física y el inventario se apilan verticalmente. La tabla del inventario se transforma en tarjetas por dispositivo para evitar depender de desplazamiento horizontal y conservar visibles el nombre, modelo, posición, serial, IP principal, estado y acceso a la ficha.
