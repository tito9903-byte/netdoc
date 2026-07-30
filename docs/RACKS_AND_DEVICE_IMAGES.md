# Racks, vistas 2D/3D e imágenes de modelos

## Objetivo

NetDoc presenta la instalación física documentada en NetBox sin mantener un inventario paralelo. NetBox conserva fabricante, modelo, dimensiones, componentes, dispositivos, rack, cara y posición. NetDoc conserva únicamente las imágenes frontal y trasera cuando se cargan desde su interfaz.

La asociación se realiza mediante el identificador numérico `device_type_id` del modelo en NetBox. Las imágenes no alteran el modelo ni se copian a cada dispositivo.

## Flujo recomendado

1. Crear el modelo desde **Modelos de equipos → Crear modelo**.
2. Definir fabricante, modelo, part number, altura en U y profundidad.
3. Adjuntar opcionalmente una imagen frontal y una imagen trasera en el mismo formulario.
4. Crear las plantillas de interfaces y puertos en **Plantillas de puertos**.
5. Crear el dispositivo usando el modelo.
6. Seleccionar sitio, rack, posición U y cara.
7. Revisar el rack alternando entre vista 2D y vista 3D.

## Separación de responsabilidades

| Dato | Sistema responsable |
|---|---|
| Fabricante, modelo, slug y part number | NetBox |
| `u_height`, profundidad y componentes | NetBox |
| Dispositivos, rack, cara y posición | NetBox |
| Imagen frontal y trasera cargadas desde NetDoc | Base local de NetDoc |
| Imágenes antiguas ya presentes en NetBox | NetBox, como fallback de lectura |

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

Cada archivo puede pesar hasta 5 MB. NetDoc valida:

- nombre de archivo;
- tamaño;
- tipo MIME declarado;
- firma binaria real del archivo;
- correspondencia entre el tipo declarado y el contenido.

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

Existe una restricción única por `(device_type_id, face)`, por lo que subir otra imagen para la misma cara sustituye el registro anterior.

Las consultas de catálogo solo recuperan metadatos; no cargan los binarios de todas las imágenes en memoria. El binario se lee únicamente al solicitar la ruta de medios.

## Sustitución posterior de imágenes

Las imágenes se administran desde:

```text
/device-types/{device_type_id}/images
```

La escritura local requiere:

- sesión autenticada;
- permiso `devices.create`;
- token CSRF válido;
- que el `device_type_id` todavía exista en NetBox.

No requiere que NetBox pueda escribir en `MEDIA_ROOT` y no ejecuta una modificación sobre NetBox.

## Entrega de imágenes

La ruta autenticada es:

```text
/media/device-types/{device_type_id}/{front|rear}
```

Orden de lectura:

1. imagen local de NetDoc;
2. imagen ya documentada en NetBox, cuando no existe una copia local;
3. representación alternativa con nombre y modelo, cuando ninguna existe.

La respuesta utiliza:

- `Content-Type` validado;
- `X-Content-Type-Options: nosniff`;
- caché privada;
- `ETag` derivado del SHA-256.

El token de NetBox nunca se entrega al navegador.

## Uso dentro del rack

La elevación selecciona la imagen según la cara activa:

- cara `front`: usa la imagen frontal;
- cara `rear`: usa la imagen trasera;
- si la cara no tiene imagen, presenta una representación alternativa con nombre y modelo.

La imagen se ajusta al espacio físico del dispositivo; no modifica la cantidad de unidades ocupadas. La ocupación proviene de `u_height` del modelo y de la posición del dispositivo.

## Espacio de trabajo del rack

El detalle organiza la elevación 3D y el inventario en un mismo espacio de
trabajo. El panel lateral permite buscar por nombre, modelo, dirección IP,
serial, posición o estado sin volver a consultar NetBox.

Cada fila muestra dispositivo, modelo, posición y cara, número de serie, IP
principal, estado y acceso a la ficha. En pantallas pequeñas, la tabla se transforma en tarjetas por dispositivo para conservar las etiquetas y evitar desplazamiento horizontal.

El botón **Descargar reporte PDF** genera en memoria una sola página con el
resumen del rack, la elevación 3D con fotografías y el inventario. El archivo no
se almacena en el servidor.

## Alturas y ocupación

NetDoc utiliza la altura documentada en el modelo:

- `0U`: no consume espacio vertical;
- `0.5U`: ocupa media unidad;
- `1U`, `2U`, `6U`, etc.: ocupan la cantidad correspondiente;
- `is_full_depth=true`: el equipo aparece en ambas caras;
- los solapamientos físicos se marcan como conflicto;
- los equipos sin posición válida se muestran fuera de la elevación.

No se debe inferir una altura por el nombre o por la fotografía. Antes de colocar el dispositivo, el modelo debe tener un `u_height` correcto.

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
4. Abrir la URL de medios autenticada y confirmar HTTP 200.
5. Revisar el mismo modelo en el catálogo, ficha, rack 2D y rack 3D.
6. Sustituir la imagen y confirmar que cambia el `ETag`.
7. Confirmar el evento en Auditoría.
8. Confirmar que el modelo y sus dimensiones en NetBox no fueron alterados.
