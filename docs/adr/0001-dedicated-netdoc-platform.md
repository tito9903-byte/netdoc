# ADR 0001: NetDoc como plataforma dedicada

- **Estado:** Aceptado
- **Fecha:** 2026-07-24

## Contexto
NetDoc requiere decisiones explícitas y mantenibles para su evolución.

## Problema
Definir una dirección estable sin inventar hechos no verificados.

## Decisión
NetDoc se ejecuta en un servidor dedicado exclusivamente al proyecto.

## Alternativas consideradas
Evaluar otras aplicaciones en el servidor o compartirlo.

## Consecuencias positivas
Mayor aislamiento, servicios exclusivamente de NetDoc, menor interferencia y desarrollo/producción separados en el mismo servidor.

## Consecuencias negativas
Concentración de riesgo en un servidor dedicado.

## Riesgos
Cambios no documentados, configuración inconsistente o validación insuficiente.

## Medidas de mitigación
Documentar operación, separar servicios y evaluar formalmente cualquier instalación futura.

## Referencias internas
[Estado del proyecto](../PROJECT_STATUS.md), [arquitectura](../ARCHITECTURE.md), [seguridad](../SECURITY.md).
