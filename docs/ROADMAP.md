# Roadmap

No hay fechas comprometidas. La fuente oficial del estado es [PROJECT_STATUS](PROJECT_STATUS.md).

| Fase | Estado | Objetivo, entregables, dependencias, riesgos y aceptación |
|---|---|---|
| 0 Base | Completado | Base FastAPI, configuración y autenticación inicial; depende de configuración segura; aceptar importación y configuración documentada. |
| 1 Consulta documental | Completado | Dashboard, dispositivos, interfaces y racks; depende de NetBox; riesgo de conectividad; aceptar consultas operativas verificadas. |
| 2 Escritura controlada | Completado | Creación guiada de equipos y cables; depende de permisos NetBox; riesgo de escritura; aceptar controles y pruebas manuales. |
| 3 Usuarios, roles, permisos y auditoría | En progreso | Identidad persistente, RBAC, administración, perfil, bloqueo de login, eliminación controlada, filtros y exportación de auditoría en `feature/access-control-audit`; depende de prueba integral en desarrollo. |
| 3.1 Migraciones y ciclo de vida de identidad | En progreso | Alembic, revisión inicial `20260724_0001`, adopción de base heredada completa y rechazo de esquemas parciales implementados; faltan respaldo/recuperación automatizados, retención de auditoría y validación operativa en 8101. |
| 4 Patch panels y gestión física avanzada | Planificado | Patch panels y puertos; depende de fase 3; riesgo de modelo; aceptar representación y validaciones. |
| 5 Búsqueda global y topología | En progreso | Búsqueda global inicial implementada para dispositivos, interfaces, racks, sitios y cables; topologías física y lógica permanecen planificadas. |
| 6 Visualización avanzada y 3D | Planificado | 3D; depende de topología; riesgo de complejidad; aceptar usabilidad y rendimiento. |
| 7 Pruebas, observabilidad y fortalecimiento | En progreso transversal | Suite automatizada con 27 pruebas, validación del grafo Alembic y módulo Sistema de solo lectura incorporados; faltan métricas históricas, alertas, errores centralizados, MFA, rate limiting distribuido y más pruebas de seguridad. |