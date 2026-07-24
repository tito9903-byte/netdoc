# Pruebas

## Estado actual

El repositorio incluye pruebas de servicios de acceso y rutas administrativas en `tests/`. Las validaciones generales continúan siendo compilación, importación de `app.main`, sintaxis Bash, revisión de plantillas y pruebas manuales en desarrollo. Las pruebas HTTP contra los puertos del servidor deben ejecutarse únicamente en el servidor autorizado.

| Módulo | Cobertura actual | Pendiente |
|---|---|---|
| Autenticación y roles | Inicialización, usuario, contraseña, permisos, persistencia y autorización web | bloqueo, revocación de sesiones y concurrencia |
| Usuarios administrativos | Login, acceso de administrador y denegación de Consulta | formularios completos, último administrador, CSRF inválido y cambio de contraseña |
| Auditoría | Creación, persistencia y login fallido visible | filtros, retención, exportación y carga |
| Dispositivos/interfaces | Manual | unitarias e integración con NetBox simulado |
| Creación/cables | Validación manual existente | autorización, CSRF, errores y regresión |
| Racks | Manual | datos de borde y UI |
| Despliegue | Sintaxis y ejecución manual conocida | ensayo del nuevo esquema y respaldo |

## Comandos

```bash
python -m compileall app tests
python -m unittest discover -s tests -v
python -c 'from app.main import app; print(app.title)'
bash -n scripts/netdoc-deploy-dev
bash -n scripts/netdoc-deploy-prod
```

## Resultados de la rama `feature/access-control-audit`

Se ejecutaron en un entorno aislado, no en el servidor:

- Compilación de los módulos Python nuevos y modificados: correcta.
- Inicialización de SQLite en memoria y archivo temporal: correcta.
- Creación de nueve permisos y tres roles iniciales: correcta.
- Creación y autenticación de usuarios de prueba: correcta.
- Rechazo de contraseña débil: correcto.
- Creación de rol personalizado y evento de auditoría: correcta.
- Persistencia de permisos personalizados del rol Operador tras repetir la inicialización: correcta.
- Carga sintáctica de todas las plantillas administrativas: correcta.
- Ocho pruebas automatizadas: superadas localmente.
- TestClient: login administrativo y acceso a Usuarios, Roles y Auditoría: correctos.
- TestClient: rol Consulta redirigido a `/forbidden` al intentar administrar usuarios: correcto.
- TestClient: intento de login fallido visible en Auditoría: correcto.

## Integración continua

`.github/workflows/ci.yml` instala `requirements-lock.txt`, compila `app` y `tests`, ejecuta la suite, importa `app.main`, analiza todas las plantillas Jinja2 y valida los scripts de despliegue. El workflow `NetDoc CI` del PR #3 completó correctamente instalación, compilación, pruebas, importación, plantillas y scripts.

Estos resultados no validan systemd, el puerto 8101, la base persistente real del servidor, el navegador con datos reales ni NetBox.

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
10. Revisar logs, permisos del archivo de base y que Git lo ignore.

## Estrategia siguiente

Agregar pruebas de formularios completos, CSRF inválido, protección del último administrador, cambios de rol, filtros de auditoría, fallos de base, integración simulada con NetBox y migraciones. Antes de `main`: diff y documentación revisados, pruebas existentes, despliegue en desarrollo, revisión de permisos y validación manual del propietario sin inventar resultados.
