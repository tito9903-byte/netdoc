# Estado del proyecto: NetDoc

- **Propósito:** interfaz operativa para consultar, crear y visualizar inventario de red cuyo origen oficial es NetBox.
- **Estado general:** En progreso.
- **Última actualización:** 2026-07-24.
- **Versión documental:** 1.0.
- **Responsable / repositorio:** responsable del proyecto / `tito9903-byte/netdoc`.
- **Ramas:** producción `main`; desarrollo `develop`.

## Resumen ejecutivo

La base web, consulta documental, operaciones de escritura guiadas y racks 2D
están presentes en el código. Esta actualización establece la documentación y
los scripts de despliegue; no ejecutó servicios ni cambios en el servidor.

## Entornos y servicios

| Entorno | Estado documental | Ruta | Rama | Servicio | Puerto | Sesión |
|---|---|---|---|---|---:|---|
| Producción | Requiere verificación | `/opt/netdoc-prod` | `main` | `netdoc-prod` | 8100 | independiente |
| Desarrollo | Requiere verificación | `/opt/netdoc-dev` | `develop` | `netdoc-dev` | 8101 | `netdoc_dev_session` |

Servidor dedicado: `192.168.10.93`; NetBox configurado: `https://192.168.10.95`. Desarrollo debe usar `NETBOX_WRITE_ENABLED=false`. El respaldo temporal
`/opt/netbox-documental` no es producción activa y requiere decisión formal
antes de eliminarse.

## Arquitectura, tecnologías e integración

FastAPI sirve HTML Jinja2 y estáticos; routers y servicios consumen REST de
NetBox con HTTPX. Configuración con Pydantic Settings, sesiones con
SessionMiddleware y autenticación inicial basada en Argon2. Véanse
[arquitectura](ARCHITECTURE.md) e [integración](NETBOX_INTEGRATION.md).

## Módulos

- **Completado:** autenticación administrativa inicial, dashboard, consulta,
búsqueda/filtros/paginación/detalle de dispositivos e interfaces, creación
guiada de equipos, consulta y creación de cables, listado/rack 2D, selector de
detalle e inspector de equipos, API REST NetBox y sesiones configurables.
- **En progreso:** documentación como código y flujo de despliegue revisable.
- **Planificado:** usuarios, roles, permisos, auditoría, edición/eliminación
controlada, patch panels/puertos, edición/desconexión de cables, búsqueda,
topologías, 3D, validaciones, errores centralizados, pruebas, seguridad y
observabilidad.
- **Bloqueado:** ninguno registrado.
- **Diferido:** eliminación del respaldo temporal.

## Deuda, problemas y riesgos

Las pruebas automatizadas y auditoría interna están planificadas. La
confirmación funcional de servicios, permisos y conectividad NetBox requiere
verificación en servidor. Riesgos: tokens amplios, errores de despliegue y
cambios no probados; las mitigaciones están en [seguridad](SECURITY.md) y
[despliegue](DEPLOYMENT.md).

## Decisiones, seguridad, despliegue, pruebas y documentación

Los ADR aceptados cubren plataforma dedicada, separación de entornos, NetBox
como fuente oficial y documentación como código. Seguridad: configuración
sensible fuera de Git y escritura deshabilitada en desarrollo. Despliegue:
scripts con validación, rechazo de árbol Git no limpio y rollback documentados, sin ejecución verificada aquí.
Pruebas: no se identificó suite automatizada versionada; consulte
[TESTING](TESTING.md). Documentación: Completado para esta base.

## Próximo objetivo

**Planificado:** usuarios, roles, permisos y auditoría. Aceptación: diseño
aprobado mediante ADR cuando corresponda, mínimo privilegio, auditoría de
acciones, pruebas y documentación actualizada.

## Hitos y referencias

No se inventan fechas históricas; este documento registra el hito documental
del 2026-07-24. Consulte [roadmap](ROADMAP.md), [operaciones](OPERATIONS.md),
[glosario](GLOSSARY.md) y el [índice](README.md).

## Reglas de mantenimiento del documento

Actualice este documento en todo PR que modifique funcionalidades, arquitectura,
seguridad, despliegues, dependencias, módulos, estado de pruebas, riesgos,
prioridades, problemas conocidos o decisiones técnicas. Use solo: **Completado**,
**En progreso**, **Planificado**, **Bloqueado**, **Diferido** o **Requiere verificación**.
