# Roadmap

No hay fechas comprometidas. La fuente oficial del estado es
[PROJECT_STATUS](PROJECT_STATUS.md).

| Fase | Estado | Objetivo, entregables, dependencias, riesgos y aceptación |
|---|---|---|
| 0 Base | Completado | Base FastAPI, configuración y autenticación; depende de configuración segura; aceptar importación y configuración documentada. |
| 1 Consulta documental | Completado | Dashboard, dispositivos, interfaces y racks; depende de NetBox; riesgo de conectividad; aceptar consultas operativas verificadas. |
| 2 Escritura controlada | Completado | Creación guiada de equipos/cables; depende de permisos NetBox; riesgo de escritura; aceptar controles y pruebas manuales. |
| 3 Usuarios, roles, permisos y auditoría | Planificado | Próximo módulo: identidad, autorización y trazabilidad; depende de diseño/ADR; riesgo de privilegios; aceptar mínimo privilegio y pruebas. |
| 4 Patch panels y gestión física avanzada | Planificado | Patch panels y puertos; depende de fase 3; riesgo de modelo; aceptar representación y validaciones. |
| 5 Búsqueda global y topología | Planificado | Búsqueda y topologías física/lógica; depende de datos; riesgo de rendimiento; aceptar resultados verificables. |
| 6 Visualización avanzada y 3D | Planificado | 3D; depende de topología; riesgo de complejidad; aceptar usabilidad y rendimiento. |
| 7 Pruebas, observabilidad y fortalecimiento | Planificado | pytest, errores centralizados, registros y seguridad; depende de cobertura; riesgo de regresiones; aceptar automatización y métricas. |
