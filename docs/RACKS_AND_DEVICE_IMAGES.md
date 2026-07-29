# Racks, vistas 2D/3D, imágenes y reportes

## Objetivo

NetDoc presenta la instalación física documentada en NetBox sin mantener un inventario paralelo. NetBox conserva fabricante, modelo, dimensiones, componentes, dispositivos, rack, cara y posición. NetDoc conserva únicamente las imágenes frontal y trasera cuando se cargan desde su interfaz.

La asociación se realiza mediante el identificador numérico `device_type_id` del modelo en NetBox. Las imágenes no alteran el modelo ni se copian a cada dispositivo.

## Flujo recomendado

1. Crear el modelo desde **Modelos de equipos → Crear modelo**.
2. Definir fabricante, modelo, part number, altura en U y profundidad.
3. Adjuntar opcionalmente una imagen frontal y una imagen trasera.
4. Crear las plantillas de interfaces y puertos en **Plantillas de puertos**.
5. Crear el dispositivo usando el modelo.
6. Seleccionar sitio, rack, posición U y cara.
7. Abrir el rack y alternar entre vista 2D y vista 3D.
8. Descargar el reporte PDF para conservar la elevación y el inventario.

La opción 3D solo se muestra dentro del detalle de un rack. El catálogo `/racks` sirve para localizar y abrir el bastidor; no contiene una topología 3D global independiente.

## Separación de responsabilidades

| Dato | Sistema responsable |
|---|---|
| Fabricante, modelo, slug y part number | NetBox |
| `u_height`, profundidad y componentes | NetBox |
| Dispositivos, rack, cara y posición | NetBox |
| Imagen frontal y trasera cargadas desde NetDoc | Base local de NetDoc |
| Imágenes antiguas ya presentes en NetBox | NetBox, como fallback de lectura |
| Reporte PDF descargado | Generado bajo demanda por NetDoc |

NetBox admite imágenes frontal y trasera para tipos de dispositivo, pero sus archivos dependen de `MEDIA_ROOT` y de los permisos del proceso que ejecuta NetBox. El almacenamiento local evita que una falla de permisos en ese directorio impida documentar la representación visual del equipo.

## Imágenes durante la creación del modelo

El formulario `GET /device-types/new` envía un formulario `multipart/form-data` a:

```text
POST /device-types/actions/create-with-images
```

Campos opcionales:

- `front_image`: representación frontal del modelo;
- `rear_image`: representación trasera del modelo.

Formatos admitidos:

- JPG;
- PNG;
- WEBP;
- GIF.

Cada archivo puede pesar hasta 5 MB. NetDoc valida nombre, tamaño, tipo MIME declarado, firma binaria real y correspondencia entre el tipo declarado y el contenido.

La operación se ejecuta en dos fases:

1. NetDoc crea el tipo de dispositivo mediante la API REST de NetBox.
2. Si se seleccionaron imágenes, NetDoc las guarda en la tabla local `device_type_images` usando el ID devuelto por NetBox.

Si el modelo se crea pero falla la persistencia local, el modelo se conserva, el resultado queda en auditoría y el usuario puede repetir únicamente la carga de imágenes desde la galería.

## Esquema local

La migración Alembic `20260725_0002` agrega la tabla `device_type_images`.

Cada registro conserva:

- `device_type_id` externo de NetBox;
- cara `front` o `rear`;
- nombre seguro;
- tipo de contenido;
- binario de la imagen;
- tamaño;
- hash SHA-256;
- fecha y usuario de la última actualización.

Existe una restricción única por `(device_type_id, face)`, por lo que subir otra imagen para la misma cara sustituye el registro anterior. Las consultas de catálogo solo recuperan metadatos; no cargan todos los binarios en memoria.

## Agregar o reemplazar imágenes

Las imágenes se administran desde:

```text
/device-types/{device_type_id}/images
```

El usuario puede seleccionar únicamente la cara que desea cambiar. Una cara no seleccionada conserva su archivo actual. La escritura local requiere:

- sesión autenticada;
- permiso `devices.create`;
- token CSRF válido;
- que el `device_type_id` todavía exista en NetBox.

No requiere que NetBox pueda escribir en `MEDIA_ROOT` y no ejecuta una modificación sobre NetBox.

## Entrega y actualización de imágenes

La ruta autenticada es:

```text
/media/device-types/{device_type_id}/{front|rear}
```

Orden de lectura:

1. imagen local de NetDoc;
2. imagen ya documentada en NetBox cuando no existe una copia local;
3. representación alternativa con nombre y modelo cuando ninguna existe.

La respuesta utiliza `Content-Type` validado, `X-Content-Type-Options: nosniff`, caché privada con revalidación y `ETag` derivado del SHA-256. La revalidación evita que el navegador conserve durante varios minutos una fotografía que acaba de ser reemplazada.

El token de NetBox nunca se entrega al navegador.

## Ajuste visual de fotografías

Las vistas 2D y 3D ajustan la fotografía al 100% del ancho y de la altura física asignada al equipo mediante `object-fit: fill`. Este ajuste puede cambiar la proporción visual, pero no recorta la imagen, no deja espacios internos y no altera la posición, la unidad inicial ni `u_height`.

La ruta de medios entrega directamente los bytes originales, tanto para imágenes locales como para las obtenidas desde NetBox. No recorta, reencodifica ni almacena representaciones derivadas.

Para obtener el mejor resultado:

- usar orientación horizontal cuando sea posible;
- usar una fotografía diferente para frente y parte trasera;
- documentar correctamente `u_height`, porque la fotografía no determina el espacio ocupado.

En equipos de 0.5U o 1U, el modo **Detalle** de la vista 3D aumenta la altura del gabinete para que la fotografía resulte más legible. Los nombres de equipos bajos se consultan mediante el inspector lateral y el tooltip, evitando cubrir la imagen.

## Vista 3D estilo datacenter

La vista 3D se selecciona exclusivamente dentro de:

```text
/racks/{rack_id}?view=3d
```

Incluye:

- gabinete metálico con profundidad y rieles;
- fondo y piso técnico estilo datacenter;
- perspectiva isométrica o frontal;
- cara frontal o trasera;
- escala **Ajustar** o **Detalle**;
- fotografías sin deformación;
- indicadores visuales de equipos con imagen;
- conflictos de posición en rojo;
- inspector lateral compartido con la vista 2D.

La visualización es una representación documental. No sustituye una medición física ni corrige automáticamente posiciones erróneas en NetBox.

## Alturas y ocupación

NetDoc utiliza la altura documentada en el modelo:

- `0U`: no consume espacio vertical;
- `0.5U`: ocupa media unidad;
- `1U`, `2U`, `6U`, etc.: ocupan la cantidad correspondiente;
- `is_full_depth=true`: el equipo aparece en ambas caras;
- los solapamientos físicos se marcan como conflicto;
- los equipos sin posición válida se muestran fuera de la elevación.

No se debe inferir una altura por el nombre o por la fotografía. Antes de colocar el dispositivo, el modelo debe tener un `u_height` correcto.

## Reporte PDF del rack

Cada rack ofrece:

```text
GET /racks/{rack_id}/report.pdf?face={front|rear}
```

El reporte se genera bajo demanda y requiere permiso `racks.view`. No se guarda una copia permanente en la base.

Contenido:

- nombre, sitio, ubicación y estado del rack;
- altura, unidades ocupadas, libres y porcentaje de utilización;
- elevación de la cara seleccionada;
- equipos posicionados y conflictos;
- inventario paginado con equipo, modelo, posición, altura, cara, estado, serial, etiqueta de activo y disponibilidad de fotografía;
- equipos de 0U y equipos sin posición válida.

El PDF se construye con primitivas internas y fuentes estándar, por lo que no agrega dependencias nativas al servidor. La elevación del reporte utiliza bloques y etiquetas para mantener legibilidad de impresión; la interfaz web conserva las fotografías completas.

## Respaldo y capacidad

Las imágenes forman parte de `DATABASE_URL`. Por tanto:

- el respaldo de la base local incluye usuarios, roles, auditoría e imágenes;
- la base crecerá según la cantidad y el tamaño de los archivos;
- no se debe copiar la base de desarrollo sobre producción;
- antes de una migración o despliegue debe crearse un respaldo consistente;
- para muchos miles de imágenes se deberá evaluar PostgreSQL u almacenamiento de objetos, manteniendo la misma interfaz de servicio.

Con el límite actual de dos imágenes de hasta 5 MB por modelo, SQLite es adecuado para el tamaño inicial del proyecto, siempre que existan respaldos y espacio suficiente.

## Auditoría

Se registran, como mínimo:

- `DEVICE_TYPE_CREATE` para la creación del modelo en NetBox;
- `DEVICE_TYPE_IMAGE_UPDATE` para la carga o sustitución local;
- resultado correcto o fallido;
- usuario, IP, agente de usuario y modelo afectado.

No se registra el contenido binario ni el token de NetBox.

## Validación

Antes de fusionar:

```bash
scripts/netdoc-test-isolated
python -m compileall -q app tests migrations
python -c 'from app.main import app; print(app.title, len(app.routes))'
```

Prueba manual en desarrollo:

1. Confirmar que Alembic presenta `20260725_0002` como cabeza.
2. Abrir un modelo existente y cargar una imagen frontal.
3. Confirmar que la galería indica **Guardada en NetDoc**.
4. Sustituir la imagen y confirmar que cambia inmediatamente al recargar.
5. Revisar el modelo en catálogo, ficha, rack 2D y rack 3D.
6. Alternar **Ajustar** y **Detalle** en un rack de 42U.
7. Verificar fotografías de equipos de 1U y alturas mayores.
8. Descargar el PDF y revisar elevación, inventario y paginación.
9. Confirmar auditoría y que el modelo y sus dimensiones en NetBox no fueron alterados.
