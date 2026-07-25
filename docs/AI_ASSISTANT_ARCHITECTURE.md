# Arquitectura del asistente de documentación

## Visión

El asistente permitirá que un usuario describa una tarea con lenguaje natural y reciba una guía dentro de NetDoc. Su objetivo no es reemplazar NetBox ni otorgar libertad ilimitada a un modelo de lenguaje. La IA interpreta la intención; servicios deterministas resuelven, validan y ejecutan.

Ejemplos futuros:

```text
Quiero documentar una nueva OLT C600 en Samaná.
```

```text
Conecta el puerto Ethernet1 del CORE-01 con uplink-1 de OLT-SMN-01.
```

```text
Necesito un pool /24 para clientes corporativos en la VRF INTERNET-SMN.
```

## Límite de confianza

```text
Usuario
  ↓
Asistente conversacional
  ↓ produce intención estructurada, nunca HTTP libre
Orquestador de flujos
  ↓
Resolutores de NetBox
  ↓
Plan seguro y preguntas
  ↓
Motor de políticas y permisos
  ↓
Confirmación humana
  ↓
Ejecutor REST permitido
  ↓
Verificación y auditoría
```

La salida de la IA se considera entrada no confiable. No puede proporcionar directamente:

- URL de API;
- método HTTP;
- ID final de un objeto;
- permiso requerido;
- código Python o SQL para ejecutar;
- decisión de omitir confirmación.

Esos valores provienen exclusivamente del código versionado.

## Capas

### 1. Interpretación

Convierte el mensaje en una intención limitada, por ejemplo:

```json
{
  "intent": "connect_cable",
  "endpoint_a": {
    "device": "CORE-01",
    "interface": "Ethernet1"
  },
  "endpoint_b": {
    "device": "OLT-SMN-01",
    "interface": "uplink-1"
  },
  "cable_type": "smf-os2"
}
```

El esquema se valida estrictamente. Campos desconocidos se rechazan.

### 2. Resolución

Busca objetos reales mediante la API de NetBox.

- Cero coincidencias: informa que el objeto no existe.
- Una coincidencia: conserva ID y estado actual.
- Varias coincidencias: pregunta al usuario mostrando sitio, tenant, rack u otro contexto.

La IA no selecciona silenciosamente la primera coincidencia.

### 3. Recolección guiada

Cada flujo define datos obligatorios y opcionales. El asistente pregunta únicamente lo necesario y puede abrir componentes visuales de NetDoc para facilitar la selección.

Ejemplo para un equipo:

1. fabricante y modelo;
2. nombre;
3. rol y plataforma;
4. sitio y localidad;
5. rack, cara y posición;
6. tenant y estado;
7. datos opcionales;
8. vista previa.

### 4. Planificación

El orquestador llama a un planificador determinista. `ChangePlan` contiene operaciones conocidas, advertencias, preguntas y una huella inmutable.

La IA explica el plan en lenguaje natural, pero no puede modificar el payload después de la validación.

### 5. Políticas

Antes de permitir la confirmación se verifica:

- autenticación de NetDoc;
- permiso del usuario;
- `NETBOX_WRITE_ENABLED`;
- capacidad registrada;
- permiso efectivo del token en NetBox;
- esquema `OPTIONS` de la versión instalada;
- reglas específicas del módulo;
- estado actual de los objetos;
- límites de cantidad y riesgo.

### 6. Confirmación

La pantalla muestra:

- objetos que se crearán o modificarán;
- valores anteriores y nuevos;
- dependencias;
- advertencias;
- efectos parciales posibles;
- frase de confirmación ligada a la huella.

Las acciones de mayor impacto requerirán una segunda confirmación o revisión administrativa.

### 7. Ejecución y verificación

El ejecutor solo acepta instancias de `ChangePlan` validadas. Después de cada solicitud:

- comprueba el código HTTP;
- interpreta errores de campo;
- vuelve a consultar el objeto;
- compara el resultado esperado;
- registra auditoría;
- detiene dependencias cuando ocurre un fallo.

## Flujo de conexión de cable

### Conversación

```text
Usuario: Conecta Ethernet1 de CORE-01 con uplink-1 de OLT-SMN-01.

Asistente: Encontré ambos equipos. Ethernet1 está libre. Encontré dos interfaces
llamadas uplink-1 en OLT-SMN-01: una física y una virtual. ¿Cuál deseas usar?

Usuario: La física SFP+.

Asistente: Preparé este cambio:
- A: CORE-01 · Ethernet1
- B: OLT-SMN-01 · uplink-1
- Tipo: sin especificar
- Estado: conectado
¿Deseas indicar tipo, etiqueta, color o longitud?

Usuario: Fibra OS2, etiqueta FO-SMN-001, 125 metros.

Asistente: El plan creará un cable y no modificará otros objetos. Confirma el plan.
```

### Validaciones específicas

- ambos dispositivos existen y son visibles para el usuario;
- ambas terminaciones existen;
- los extremos están libres al generar y al ejecutar el plan;
- no son el mismo objeto;
- NetBox acepta esa combinación de terminaciones;
- tipo, estado y unidad pertenecen a las opciones de la instalación;
- no hubo un cambio concurrente;
- el usuario tiene permiso;
- el token técnico puede agregar cables;
- la escritura está habilitada;
- el plan confirmado no cambió.

## Memoria y privacidad

La conversación puede conservar referencias funcionales durante la sesión, pero:

- no almacena tokens ni secretos;
- no agrega datos inventados a NetBox;
- no usa una conversación como autorización permanente;
- no revela objetos que el usuario no puede consultar;
- redacta valores sensibles en trazas y auditoría;
- separa el historial conversacional de la fuente oficial.

## Estrategia de implementación

### Etapa 1: fundamento

- planes de cambio;
- lista cerrada de capacidades;
- planificador de cables;
- documentación y pruebas;
- sin interfaz de chat ni ejecución automática.

### Etapa 2: asistente de solo lectura

- chat para buscar y explicar inventario;
- preguntas guiadas;
- enlaces a las pantallas correctas;
- generación de planes sin ejecutar.

### Etapa 3: confirmación de una operación

- resolver y crear cables;
- mostrar vista previa;
- ejecutar solo después de confirmación;
- verificar y auditar.

### Etapa 4: flujos compuestos

- alta de sitio, rack, modelo y dispositivo;
- plantillas de componentes;
- VLAN, prefijo, dirección y servicio;
- circuitos y terminaciones;
- manejo explícito de resultados parciales.

### Etapa 5: recomendaciones

- detectar documentación incompleta;
- sugerir estándares internos;
- guiar correcciones;
- nunca aplicar recomendaciones sin revisión.

## Pruebas del asistente

Se mantendrá un conjunto de conversaciones de referencia que cubra:

- nombres ambiguos;
- objetos inexistentes;
- falta de permisos;
- endpoint ocupado;
- información incompleta;
- intento de eliminación;
- prompt injection para obtener tokens o ejecutar endpoints arbitrarios;
- cambio concurrente después de confirmar;
- fallo parcial;
- respuesta inesperada de un plugin;
- diferencias entre versiones de NetBox.
