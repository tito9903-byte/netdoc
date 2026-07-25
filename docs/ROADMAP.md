# Roadmap

No hay fechas comprometidas. La fuente oficial del estado es [PROJECT_STATUS](PROJECT_STATUS.md) y la cobertura funcional se detalla en [NETBOX_MODULE_COVERAGE](NETBOX_MODULE_COVERAGE.md).

| Fase | Estado | Objetivo, dependencias, riesgos y aceptación |
|---|---|---|
| 0 Base | Completado | FastAPI, configuración, autenticación inicial y separación de entornos. |
| 1 Consulta documental | Completado | Dashboard, dispositivos, interfaces, conexiones y racks; aceptar consultas operativas verificadas. |
| 2 Escritura controlada inicial | Completado | Creación guiada de equipos y cables con permiso, CSRF, auditoría y bandera de escritura. |
| 3 Identidad, RBAC, auditoría y migraciones | En progreso | Identidad persistente, roles, perfil, bloqueo, exportación y Alembic; faltan retención, recuperación y permisos más granulares. |
| 4 Experiencia de documentación | En progreso | IPAM operativo, modelos, plantillas, imágenes, racks 2D/3D y navegación por procesos; falta reorganizar fabricantes/modelos/componentes como fichas administrables. |
| 5 Frontera segura de cambios | En progreso | `ChangePlan`, lista cerrada, esquema `OPTIONS`, confirmación y planificador de cables; aceptar pruebas, vista previa real y ejecutor aún deshabilitado. |
| 6 Infraestructura física avanzada | Planificado | Patch panels, módulos, tarjetas, bahías, inventario, reservas de rack, energía y trazado; depende de validadores específicos. |
| 7 IPAM con escritura guiada | Planificado | VRF, VLAN, prefijos, rangos, IP, ASN, FHRP y servicios; depende de detección de solapamiento, permisos por VRF/sitio y prueba de concurrencia. |
| 8 Circuitos y proveedores | Planificado | Proveedores, cuentas, circuitos, terminaciones y conexiones físicas; aceptar alta y trazado extremo a extremo. |
| 9 Virtualización, VPN e inalámbrico | Planificado | Clústeres, VM, interfaces, túneles, IKE/IPSec, WLAN y enlaces; depende del mapa de módulos. |
| 10 Asistente de solo lectura | Planificado | Chat para buscar, explicar, recopilar datos y producir planes sin ejecutar; aceptar ambigüedad, permisos y pruebas contra prompt injection. |
| 11 Escritura conversacional limitada | Planificado | Primera operación: cable confirmado. La IA interpreta; el ejecutor determinista valida y escribe. |
| 12 Flujos conversacionales compuestos | Planificado | Modelos, equipos, racks, IPAM y circuitos en varios pasos; requiere estados parciales, idempotencia y políticas de riesgo. |
| 13 Observabilidad y fortalecimiento | En progreso transversal | Pruebas aisladas, CI y Sistema implementados; faltan métricas históricas, errores centralizados, MFA, rate limiting distribuido, rotación de token y pruebas de seguridad. |

## Criterios antes de habilitar una capacidad para IA

1. Flujo manual operativo y entendido.
2. Resolución exacta de objetos y ambigüedad.
3. Esquema `OPTIONS` validado con la instalación.
4. Permiso específico en NetDoc y NetBox.
5. Planificador determinista con pruebas.
6. Vista previa legible y confirmación ligada a huella.
7. Verificación posterior y auditoría.
8. Manejo de cambio concurrente y fallo parcial.
9. Revisión manual en desarrollo.
10. Autorización explícita antes de producción.
