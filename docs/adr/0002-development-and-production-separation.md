# ADR 0002: Separación entre desarrollo y producción

- **Estado:** Aceptado
- **Fecha:** 2026-07-24

## Contexto
NetDoc requiere decisiones explícitas y mantenibles para su evolución.

## Problema
Definir una dirección estable sin inventar hechos no verificados.

## Decisión
Desarrollo usa `develop`, `/opt/netdoc-dev`, `.venv`/`.env`, `netdoc-dev` y 8101; producción usa `main`, `/opt/netdoc-prod`, recursos independientes, `netdoc-prod` y 8100. Se prueba antes de promover.

## Alternativas consideradas
Un solo entorno y despliegues directos.

## Consecuencias positivas
Aislamiento de cambios y sesiones, validación previa.

## Consecuencias negativas
Mayor carga operativa y necesidad de coherencia.

## Riesgos
Cambios no documentados, configuración inconsistente o validación insuficiente.

## Medidas de mitigación
Scripts acotados por entorno y checklist de despliegue.

## Referencias internas
[Estado del proyecto](../PROJECT_STATUS.md), [arquitectura](../ARCHITECTURE.md), [seguridad](../SECURITY.md).
