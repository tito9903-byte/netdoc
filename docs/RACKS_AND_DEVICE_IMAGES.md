# Racks, vistas 2D/3D e imágenes de modelos

## Objetivo

NetDoc presenta la instalación física documentada en NetBox sin mantener un inventario paralelo. El modelo de equipo define las dimensiones y las imágenes reutilizables; cada dispositivo define el rack, la cara y la posición donde está instalado.

## Flujo recomendado

1. Crear el modelo desde **Modelos de equipos → Crear modelo**.
2. Definir fabricante, modelo, part number, altura en U y profundidad.
3. Adjuntar opcionalmente una imagen frontal y una imagen trasera en el mismo formulario.
4. Crear las plantillas de interfaces y puertos en **Plantillas de puertos**.
5. Crear el dispositivo usando el modelo.
6. Seleccionar sitio, rack, posición U y cara.
7. Revisar el rack alternando entre vista 2D y vista 3D.

NetBox continúa siendo la fuente oficial de todos estos datos.

## Imágenes durante la creación del modelo

El formulario `GET /device-types/new` envía un formulario `multipart/form-data` a `POST /device-types/actions/create-with-images`.

Campos opcionales:

- `front_image`: representación frontal del modelo;
- `rear_image`: representación trasera del modelo.

Formatos admitidos:

- JPG;
- PNG;
- WEBP;
- GIF.

Cada archivo puede pesar hasta 5 MB. La validación se realiza antes de crear el modelo para evitar dejar un modelo nuevo por una imagen con formato o tamaño inválido.

La operación se ejecuta en dos fases:

1. NetDoc crea el tipo de dispositivo mediante la API REST de NetBox.
2. Si se seleccionaron imágenes, NetDoc actualiza el modelo creado mediante una solicitud multipart a `/api/dcim/device-types/{id}/`.

Si el modelo se crea pero falla la carga de imágenes, NetDoc conserva el modelo, registra el resultado en auditoría y dirige al usuario a la galería del modelo para repetir únicamente la carga de imágenes.

## Sustitución posterior de imágenes

Las imágenes también pueden administrarse después desde:

```text
/device-types/{device_type_id}/images
```

Esta pantalla permite sustituir la vista frontal, la trasera o ambas sin recrear el modelo ni sus plantillas.

## Uso dentro del rack

La elevación selecciona la imagen según la cara activa:

- cara `front`: usa `front_image`;
- cara `rear`: usa `rear_image`;
- si la cara no tiene imagen, presenta una representación alternativa con nombre y modelo.

La imagen se ajusta al espacio físico del dispositivo; no modifica la cantidad de unidades ocupadas. La ocupación proviene de `u_height` del modelo y de la posición del dispositivo.

## Alturas y ocupación

NetDoc utiliza la altura documentada en el modelo:

- `0U`: no consume espacio vertical;
- `0.5U`: ocupa media unidad;
- `1U`, `2U`, `6U`, etc.: ocupan la cantidad correspondiente;
- `is_full_depth=true`: el equipo aparece en ambas caras;
- los solapamientos físicos se marcan como conflicto;
- los equipos sin posición válida se muestran fuera de la elevación.

No se debe inferir una altura por el nombre o por la fotografía. Antes de colocar el dispositivo, el modelo debe tener un `u_height` correcto.

## Seguridad y permisos

Crear modelos o cargar imágenes requiere simultáneamente:

- sesión autenticada;
- permiso `devices.create`;
- token CSRF válido;
- `NETBOX_WRITE_ENABLED=true`;
- token de NetBox con permisos suficientes para tipos de dispositivo.

Desarrollo debe permanecer con `NETBOX_WRITE_ENABLED=false` durante la revisión inicial. En ese estado se pueden abrir los formularios y revisar imágenes existentes, pero no crear ni modificar objetos.

El token de NetBox nunca se entrega al navegador. Las imágenes privadas se sirven mediante el proxy autenticado de NetDoc.

## Auditoría

Se registran, como mínimo:

- `DEVICE_TYPE_CREATE` para la creación del modelo;
- `DEVICE_TYPE_IMAGE_UPDATE` para la carga o sustitución de imágenes;
- resultado correcto o fallido;
- usuario, IP, agente de usuario y modelo afectado.

## Validación

Antes de fusionar:

```bash
scripts/netdoc-test-isolated
python -m compileall -q app tests migrations
python -c 'from app.main import app; print(app.title, len(app.routes))'
```

Prueba manual en desarrollo:

1. Confirmar que `/device-types/new` contiene ambos selectores de archivo.
2. Confirmar que el botón permanece bloqueado con escritura deshabilitada.
3. Activar escritura únicamente en un entorno autorizado.
4. Crear un modelo de prueba con altura conocida e imágenes frontal y trasera.
5. Crear sus plantillas y un dispositivo de prueba.
6. Colocarlo en un rack y verificar 2D, 3D, cara frontal y cara trasera.
7. Confirmar auditoría y que producción no fue modificada.
