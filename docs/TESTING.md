# Pruebas

## Estado actual

No se identificó una suite automatizada versionada. Las validaciones disponibles
son compilación (`python -m compileall app`), importación de `app.main`, sintaxis
Bash y revisión manual. Las pruebas HTTP contra los puertos de servidor deben
hacerse solo en el servidor autorizado, nunca inferirse desde Codex.

| Módulo | Cobertura actual | Pendiente |
|---|---|---|
| Autenticación/sesión | Manual | pytest, CSRF y seguridad |
| Dispositivos/interfaces | Manual | unitarias e integración |
| Creación/cables | Manual | permisos, errores y regresión |
| Racks | Manual | datos de borde y UI |
| Despliegue | Sintaxis local | ensayo controlado y rollback |

Estrategia futura: pytest para seguridad, routers y servicios con mocks; pruebas
de integración aisladas con NetBox, permisos mínimos, validación de secretos y
ensayos de despliegue. Antes de `main`: diff/documentación revisados,
compilación/importación, pruebas existentes y comprobación de desarrollo sin
inventar resultados.
