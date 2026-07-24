# ADR 0003: NetBox como fuente oficial del inventario

- **Estado:** Aceptado
- **Fecha:** 2026-07-24

## Contexto
NetDoc requiere decisiones explícitas y mantenibles para su evolución.

## Problema
Definir una dirección estable sin inventar hechos no verificados.

## Decisión
NetDoc no duplica el inventario principal; usa API REST. NetBox mantiene integridad técnica y permisos como capa adicional.

## Alternativas consideradas
Duplicar inventario o escribir sin API.

## Consecuencias positivas
Experiencia operativa mejorada sin perder autoridad técnica.

## Consecuencias negativas
Dependencia de disponibilidad y permisos de NetBox.

## Riesgos
Cambios no documentados, configuración inconsistente o validación insuficiente.

## Medidas de mitigación
Tokens mínimos, errores controlados y pruebas de integración futuras.

## Referencias internas
[Estado del proyecto](../PROJECT_STATUS.md), [arquitectura](../ARCHITECTURE.md), [seguridad](../SECURITY.md).
