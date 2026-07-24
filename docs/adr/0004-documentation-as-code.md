# ADR 0004: Documentación como código

- **Estado:** Aceptado
- **Fecha:** 2026-07-24

## Contexto
NetDoc requiere decisiones explícitas y mantenibles para su evolución.

## Problema
Definir una dirección estable sin inventar hechos no verificados.

## Decisión
La documentación vive en el repositorio, se revisa en PR y se actualiza con código. PROJECT_STATUS es estado oficial, ADR decisiones y AI_HANDOFF_PROMPT transferencia.

## Alternativas consideradas
Documentación externa o conversaciones como única fuente.

## Consecuencias positivas
Trazabilidad, revisión y continuidad sin historial externo.

## Consecuencias negativas
Disciplina continua requerida.

## Riesgos
Cambios no documentados, configuración inconsistente o validación insuficiente.

## Medidas de mitigación
Reglas en AGENTS, CONTRIBUTING y revisión de PR.

## Referencias internas
[Estado del proyecto](../PROJECT_STATUS.md), [arquitectura](../ARCHITECTURE.md), [seguridad](../SECURITY.md).
