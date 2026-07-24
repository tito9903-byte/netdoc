# Pruebas

## Estado actual

El repositorio incluye una primera suite unitaria en `tests/test_access_control.py`. Las validaciones generales continúan siendo compilación, importación de `app.main`, sintaxis Bash, revisión de plantillas y pruebas manuales en desarrollo. Las pruebas HTTP contra los puertos del servidor deben ejecutarse únicamente en el servidor autorizado.

| Módulo | Cobertura actual | Pendiente |
|---|---|---|
| Autenticación y roles | Inicialización, usuario, contraseña y permisos | bloqueo, revocación de sesiones y pruebas HTTP |
| Auditoría | Creación y persistencia de evento | filtros, retención, exportación y carga |
| Dispositivos/interfaces | Manual | unitarias e integración con NetBox simulado |
| Creación/cables | Validación manual existente | autorización, CSRF, errores y regresión |
| Racks | Manual | datos de borde y UI |
| Despliegue | Sintaxis y ejecución manual conocida | ensayo del nuevo esquema y respaldo |

## Comandos

```bash
python -m compileall app tests
python -m unittest tests.test_access_control -v
python -c 'from app.main import app; print(app.title)'
bash -n scripts/netdoc-deploy-dev
bash -n scripts/netdoc-deploy-prod
```

## Resultados de la rama `feature/access-control-audit`

Se ejecutaron en un entorno aislado, no en el servidor:

- Compilación de los módulos Python nuevos y modificados: correcta.
- Inicialización de SQLite en memoria: correcta.
- Creación de nueve permisos y tres roles iniciales: correcta.
- Creación y autenticación de usuario de prueba: correcta.
- Rechazo de contraseña débil: correcto.
- Creación de rol personalizado y evento de auditoría: correcta.
- Carga sintáctica de todas las plantillas administrativas: correcta.
- Cuatro pruebas unitarias: superadas.
- Middleware aislado: solicitud no autenticada a `/` redirigida al login.

Estos resultados no validan systemd, el puerto 8101, la base persistente del servidor, el navegador completo ni NetBox.

## Prueba manual requerida en desarrollo

1. Respaldar y confirmar el `DATABASE_URL` de desarrollo.
2. Desplegar únicamente `develop` en el puerto 8101.
3. Iniciar sesión con la cuenta administrativa existente.
4. Crear usuarios de los roles Administrador, Operador y Consulta.
5. Confirmar que cada menú y URL respeta sus permisos.
6. Probar creación, edición, activación y cambio de contraseña.
7. Crear y editar un rol personalizado.
8. Verificar eventos correctos y fallidos en Auditoría.
9. Confirmar que desarrollo sigue sin escritura hacia NetBox.
10. Revisar logs y que la base no aparezca en `git status`.

## Estrategia siguiente

Agregar pruebas de routers con TestClient, CSRF, protección del último administrador, cambios de rol, filtros de auditoría, fallos de base, integración simulada con NetBox y migraciones. Antes de `main`: diff y documentación revisados, pruebas existentes, despliegue en desarrollo, revisión de permisos y validación manual del propietario sin inventar resultados.
