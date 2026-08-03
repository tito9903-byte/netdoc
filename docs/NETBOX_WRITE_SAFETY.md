# Escrituras seguras hacia NetBox

## Objetivo

NetDoc facilita la documentación, pero NetBox continúa siendo la fuente oficial. Ninguna función de NetDoc, automatización futura o asistente de IA debe escribir directamente en la base de datos de NetBox. Toda modificación se realiza por la API REST para conservar validaciones, permisos, señales, historial y compatibilidad con plugins.

## Reglas obligatorias

1. **API REST únicamente.** No se usa ORM, acceso SQL, `nbshell` ni escritura directa al almacenamiento de NetBox.
2. **Lista cerrada de capacidades.** Una operación solo puede ejecutarse si existe en `app/services/netbox_capabilities.py`.
3. **Sin eliminaciones automáticas.** Los planes aceptan únicamente `POST` y `PATCH` durante esta etapa.
4. **Solo lectura por defecto.** Desarrollo conserva `NETBOX_WRITE_ENABLED=false`.
5. **Mínimo privilegio.** El token de NetBox pertenece a un usuario técnico sin privilegios de superusuario y con permisos por modelo y, cuando corresponda, por localidad, sitio, tenant o VRF.
6. **Resolución exacta.** Antes de escribir, cada relación se convierte a un ID real de NetBox. Un nombre ambiguo produce una pregunta, nunca una selección silenciosa.
7. **Esquema dinámico.** NetDoc debe consultar `OPTIONS` para conocer campos, obligatoriedad y opciones válidas de la versión instalada antes de habilitar una operación nueva.
8. **Prevalidación.** Se comprueban dependencias, duplicados, estado actual, compatibilidad y permisos antes de enviar el cambio.
9. **Vista previa y confirmación.** El usuario revisa un plan inmutable y confirma la huella de ese plan. Si cambia cualquier dato, la confirmación anterior deja de ser válida.
10. **Historial explicativo.** Toda escritura compatible incluye `changelog_message` y se registra además en la auditoría de NetDoc.
11. **Errores parciales explícitos.** NetDoc no afirma que una operación completa terminó cuando solo algunos pasos fueron aceptados.
12. **Secretos fuera de pantalla y logs.** Tokens, contraseñas, secretos y cabeceras de autorización se redactan.

## Flujo de una operación

```text
Solicitud del usuario
        ↓
Interpretación estructurada
        ↓
Resolución de objetos en NetBox
        ↓
Preguntas por datos faltantes o ambiguos
        ↓
Plan de cambios inmutable
        ↓
Permisos + esquema OPTIONS + reglas de negocio
        ↓
Vista previa legible
        ↓
Confirmación ligada a la huella del plan
        ↓
Ejecución por la API REST
        ↓
Verificación posterior + auditoría
```

## Planes de cambio

`app/services/change_plan.py` define el contrato común entre formularios, automatizaciones y el futuro asistente.

Cada paso contiene:

- acción y recurso;
- método y endpoint REST;
- payload estructurado;
- permiso requerido;
- resumen para el usuario;
- razón del cambio;
- dependencias con pasos anteriores;
- ID esperado cuando se modifica un objeto existente.

El plan genera una huella SHA-256 y una frase de confirmación. Esto evita ejecutar un plan distinto al que el usuario revisó.

## Capacidades permitidas

`app/services/netbox_capabilities.py` registra explícitamente las rutas que NetDoc conoce. La presencia de una capacidad no significa que la IA pueda ejecutarla. El campo `ai_execution_allowed` separa:

- operaciones que el asistente puede preparar solamente;
- operaciones que, después de validación y confirmación, pueden llegar a ejecutarse.

La primera capacidad preparada para ejecución asistida es la creación de un
cable. La creación humana de pools IPAM dispone de un validador específico,
vista previa y confirmación, pero conserva `ai_execution_allowed=false`.
Fabricantes, modelos, dispositivos, racks, el resto de IPAM y circuitos
permanecen en modo de preparación hasta completar sus validadores específicos.

## Conexiones de cables

`app/services/cable_planner.py` construye un plan determinista y no escribe por sí mismo. Antes de crear un cable debe confirmar:

- tipos de terminación permitidos;
- IDs válidos;
- extremos distintos;
- ausencia de cable o endpoint conectado;
- longitud no negativa;
- color hexadecimal válido;
- estado, tipo y unidad aceptados por NetBox;
- compatibilidad de los extremos según la respuesta de NetBox;
- permiso y modo de escritura;
- confirmación humana.

Ejemplo de intención:

```text
Conecta Ethernet1 de CORE-01 con uplink-1 de OLT-SMN-01 usando fibra OS2.
```

Resultado esperado antes de ejecutar:

```text
Extremo A: CORE-01 · Ethernet1
Extremo B: OLT-SMN-01 · uplink-1
Tipo: Fibra monomodo OS2
Estado: Conectado
Cambios: crear 1 cable
Advertencias: ninguna
```

## Concurrencia y cambios externos

Antes de un `PATCH`, NetDoc debe volver a consultar el objeto y comparar, como mínimo:

- ID;
- `last_updated` cuando esté disponible;
- relaciones críticas usadas para construir el plan;
- estado del endpoint o posición física.

Si el objeto cambió después de generar la vista previa, el plan se invalida y se reconstruye. No se sobrescribe silenciosamente el trabajo de otro usuario.

## Operaciones de varios pasos

Un flujo como “crear modelo, crear 48 interfaces y crear equipo” no es una transacción única de base de datos desde NetDoc. Cada paso se verifica después de ejecutarse.

- Si falla el primer paso, no se ejecutan los siguientes.
- Si falla un paso intermedio, se detiene el plan.
- Solo se aplica una compensación cuando sea segura y esté definida explícitamente.
- No se eliminan automáticamente objetos recién creados para simular rollback.
- La interfaz muestra qué objetos existen y qué parte debe reintentarse.

## Pruebas mínimas por capacidad

Antes de habilitar una nueva escritura:

- prueba unitaria del planificador;
- prueba de payload y campos obligatorios;
- prueba de duplicados y ambigüedad;
- prueba de permiso denegado;
- prueba con escritura deshabilitada;
- prueba de confirmación incorrecta;
- prueba de cambio concurrente;
- prueba de error de NetBox y respuesta parcial;
- prueba manual en desarrollo con un token de alcance limitado;
- verificación de historial en NetBox y auditoría en NetDoc.

## Prohibiciones iniciales

El asistente y los flujos automáticos no pueden:

- ejecutar `DELETE`;
- administrar usuarios, grupos, permisos o tokens de NetBox;
- ejecutar scripts arbitrarios;
- instalar plugins;
- modificar configuración del servidor;
- enviar endpoints o payloads inventados por un modelo de lenguaje;
- desactivar validaciones para forzar una escritura;
- operar en producción sin un plan revisado y una autorización explícita.
