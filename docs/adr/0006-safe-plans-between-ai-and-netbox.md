# ADR 0006: Planes seguros entre la interfaz, la IA y NetBox

- **Estado:** Aceptado
- **Fecha:** 2026-07-24

## Contexto

NetDoc debe simplificar procesos complejos de NetBox y, en una etapa futura, aceptar solicitudes en lenguaje natural. Un modelo de lenguaje puede interpretar frases de forma ambigua, producir campos inexistentes o seleccionar el objeto incorrecto. Permitirle llamar directamente a la API pondría en riesgo la calidad de la fuente oficial.

NetBox ya proporciona API REST, validación de objetos, permisos por acción y objeto, esquema mediante `OPTIONS` e historial de cambios. NetDoc debe aprovechar esas garantías en lugar de evitarlas.

## Problema

Se necesita una frontera que permita reutilizar los mismos flujos desde formularios, automatizaciones y chat sin conceder a la IA libertad para inventar endpoints, payloads o decisiones de autorización.

## Decisión

Toda operación de escritura pasa por un `ChangePlan` estructurado y versionado en código.

- La IA produce únicamente una intención limitada.
- Resolutores deterministas convierten nombres en objetos e IDs reales.
- Los planificadores construyen los pasos permitidos.
- Una lista cerrada de capacidades valida método, endpoint y permiso.
- El esquema `OPTIONS` de NetBox valida campos y opciones.
- La vista previa genera una huella inmutable.
- El usuario confirma esa huella.
- Un ejecutor separado realiza la API REST y verifica el resultado.
- `DELETE` queda fuera de los planes automáticos durante la primera etapa.
- La base de datos de NetBox nunca se modifica directamente.

## Alternativas consideradas

### Permitir llamadas REST generadas por la IA

Rechazada. Facilita el desarrollo inicial, pero no controla rutas inventadas, cambios de versión, permisos, ambigüedad ni prompt injection.

### Implementar toda la automatización como scripts internos de NetBox

Rechazada como arquitectura principal. Los scripts tienen acceso amplio al entorno de NetBox y aumentan el impacto de un error. Podrán usarse para tareas administrativas aprobadas, pero no como canal libre del asistente.

### Replicar la base de datos de NetBox en NetDoc

Rechazada. Crearía dos fuentes de verdad, problemas de sincronización y riesgo de corrupción.

### Formularios sin modelo común de cambios

Rechazada. Duplicaría validaciones y haría que la futura IA usara un camino diferente al usuario humano.

## Consecuencias positivas

- Formularios y chat reutilizan los mismos planificadores.
- La IA no controla detalles de transporte ni autorización.
- Los cambios son explicables y revisables.
- Una confirmación no sirve para ejecutar un plan modificado.
- Se puede añadir una capacidad de forma incremental con pruebas específicas.
- Las diferencias entre versiones y plugins se detectan mediante el esquema instalado.

## Consecuencias negativas

- Cada módulo requiere resolutores, validadores y pruebas antes de escribir.
- Los flujos compuestos deben manejar resultados parciales explícitamente.
- La primera versión del asistente será de solo lectura y planificación.
- Las operaciones administrativas avanzadas tardarán más en habilitarse.

## Riesgos

- Un planificador puede contener una regla incompleta.
- El objeto puede cambiar entre la vista previa y la ejecución.
- Un plugin puede devolver un esquema diferente.
- Un token demasiado amplio aumenta el impacto de un defecto.

## Mitigaciones

- pruebas unitarias y de integración por capacidad;
- comparación del estado antes de ejecutar;
- mínimo privilegio y restricciones por objeto;
- escritura deshabilitada por defecto;
- límite de pasos;
- sin eliminación automática;
- auditoría doble en NetDoc y NetBox;
- revisión manual en desarrollo antes de producción.

## Referencias internas

- `docs/NETBOX_WRITE_SAFETY.md`
- `docs/AI_ASSISTANT_ARCHITECTURE.md`
- `docs/NETBOX_MODULE_COVERAGE.md`
- `app/services/change_plan.py`
- `app/services/netbox_capabilities.py`
- `app/services/netbox_schema_service.py`
- `app/services/cable_planner.py`
