# Índice de documentación

La documentación se mantiene como código, se revisa por pull request y no
sustituye al código versionado. Actualice primero la fuente oficial indicada.

| Documento | Objetivo | Audiencia | Fuente oficial |
|---|---|---|---|
| [PROJECT_STATUS](PROJECT_STATUS.md) | Estado y prioridades | Todo el equipo | Estado actual |
| [ARCHITECTURE](ARCHITECTURE.md) | Diseño y límites | Desarrollo | Arquitectura operativa |
| [DEPLOYMENT](DEPLOYMENT.md) | Despliegue controlado | Operación | Despliegue |
| [OPERATIONS](OPERATIONS.md) | Rutinas e incidentes | Operación | Operación |
| [SECURITY](SECURITY.md) | Reglas de seguridad | Todo el equipo | Seguridad |
| [ROADMAP](ROADMAP.md) | Trabajo futuro | Producto | Planificación |
| [NETBOX_INTEGRATION](NETBOX_INTEGRATION.md) | Integración | Desarrollo | Integración |
| [NETBOX_WRITE_SAFETY](NETBOX_WRITE_SAFETY.md) | Planes, permisos y escrituras seguras | Desarrollo, seguridad y operación | Límite de escritura |
| [NETBOX_MODULE_COVERAGE](NETBOX_MODULE_COVERAGE.md) | Cobertura actual y futura de módulos | Producto y desarrollo | Mapa funcional |
| [AI_ASSISTANT_ARCHITECTURE](AI_ASSISTANT_ARCHITECTURE.md) | Asistente conversacional y ejecución guiada | Producto, desarrollo y seguridad | Arquitectura de IA |
| [RACKS_AND_DEVICE_IMAGES](RACKS_AND_DEVICE_IMAGES.md) | Racks 2D/3D, alturas e imágenes | Producto, operación y desarrollo | Flujo físico |
| [TESTING](TESTING.md) | Estrategia de pruebas | Desarrollo | Pruebas |
| [GLOSSARY](GLOSSARY.md) | Vocabulario | Todo el equipo | Terminología |
| [ADR](adr/README.md) | Decisiones | Todo el equipo | Decisiones |
| [AI handoff](AI_HANDOFF_PROMPT.md) | Transferencia de contexto | Agentes IA | Handoff |

**Lectura recomendada:** nuevos desarrolladores: `AGENTS.md`, estado,
arquitectura, seguridad, escritura segura, contribución y ADR; operación:
despliegue, operaciones, racks e imágenes y seguridad; producto: cobertura de
módulos y arquitectura del asistente; agentes IA: el prompt maestro completo y
los documentos que ordena.

Mantenga enlaces relativos, español claro, sin secretos ni resultados no
verificados. Actualice la fuente oficial junto al cambio y enlace los resúmenes;
evite duplicar datos que puedan divergir.

## Jerarquía de fuentes

1. Código y configuración versionada: comportamiento implementado.
2. ADR: decisiones de arquitectura.
3. `PROJECT_STATUS.md`: estado y prioridades.
4. `ROADMAP.md`: trabajo futuro.
5. `NETBOX_WRITE_SAFETY.md`: reglas del límite de escritura.
6. `NETBOX_MODULE_COVERAGE.md`: alcance funcional.
7. `AI_ASSISTANT_ARCHITECTURE.md`: diseño conversacional.
8. `AI_HANDOFF_PROMPT.md`: transferencia de contexto.
9. `DEPLOYMENT.md`: despliegue.
10. `OPERATIONS.md`: operación rutinaria.
11. `SECURITY.md`: reglas de seguridad.
12. `CONTRIBUTING.md`: desarrollo y colaboración.

Cuando cambie un dato, actualice primero su fuente oficial y solo después sus
resúmenes o enlaces.
