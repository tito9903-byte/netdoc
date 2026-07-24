# Pruebas

## Estado actual

El repositorio incluye pruebas de servicios de acceso, rutas administrativas, búsqueda, sistema, perfil y protección de login en `tests/`. Las validaciones generales continúan siendo compilación, importación de `app.main`, sintaxis Bash, revisión de plantillas y pruebas manuales en desarrollo. Las pruebas HTTP contra los puertos del servidor deben ejecutarse únicamente en el servidor autorizado.

| Módulo | Cobertura actual | Pendiente |
|---|---|---|
| Autenticación y roles | Inicialización, usuario, contraseña, permisos, persistencia, actualización inmediata y bloqueo temporal | concurrencia y rate limiting distribuido |
| Usuarios administrativos | Login, acceso, denegación, desactivación, cambio de rol y eliminación de otra cuenta | último administrador, autoeliminación y CSRF inválido |
| Perfil | Acceso, actualización de datos, verificación de contraseña actual y cambio de contraseña | correo inválido, CSRF inválido y sesión concurrente |
| Auditoría | Creación, login fallido, login bloqueado y exportación CSV | fechas extremas, retención y carga |
| Búsqueda global | Agrupación, enlaces seguros y consulta corta | integración real con filtros `q` de NetBox |
| Sistema | Parsers de memoria/red, carga y métricas seguras | valores de servidor real, umbrales y compatibilidad no Linux |
| Dispositivos/interfaces | Manual | unitarias e integración con NetBox simulado |
| Creación/cables | Validación manual existente | autorización, CSRF, errores y regresión |
| Racks | Manual | datos de borde y UI |
| Despliegue | Sintaxis y ejecución manual conocida | ensayo del nuevo esquema y respaldo |

## Comandos

```bash
python -m compileall app tests
python -m unittest discover -s tests -v
python -c 'from app.main import app; print(app.title, len(app.routes))'
bash -n scripts/netdoc-deploy-dev
bash -n scripts/netdoc-deploy-prod
```

## Resultados de la rama `feature/access-control-audit`

Se ejecutaron en un entorno aislado, no en el servidor:

- Compilación de los módulos Python nuevos y modificados: correcta.
- Inicialización de SQLite en memoria y archivo temporal: correcta.
- Creación de 11 permisos y tres roles iniciales: correcta.
- Creación y autenticación de usuarios de prueba: correcta.
- Rechazo de contraseña débil: correcto.
- Creación de rol personalizado y evento de auditoría: correcta.
- Persistencia de permisos personalizados del rol Operador tras repetir la inicialización: correcta.
- Carga sintáctica de 19 plantillas: correcta.
- Importación de la aplicación con 41 rutas: correcta.
- 24 pruebas automatizadas: superadas localmente y por GitHub Actions.
- TestClient: login administrativo y acceso a Usuarios, Roles y Auditoría: correctos.
- TestClient: rol Consulta redirigido a `/forbidden` al intentar administrar usuarios: correcto.
- TestClient: intento de login fallido visible en Auditoría: correcto.
- TestClient: cinco fallos recientes bloquean temporalmente el siguiente intento y devuelven HTTP 429 con `Retry-After`: correcto.
- Servicio de acceso: fallos expirados o procedentes de otra IP no bloquean: correcto.
- TestClient: la desactivación invalida una sesión existente en la siguiente solicitud: correcto.
- TestClient: el cambio de rol actualiza permisos en la siguiente solicitud: correcto.
- TestClient: eliminación controlada de otra cuenta y exportación CSV: correctas.
- TestClient: Consulta puede usar Búsqueda y no puede abrir Sistema: correcto.
- TestClient: perfil disponible, edición de nombre/correo y cambio de contraseña propia: correctos.
- TestClient: contraseña actual incorrecta impide el cambio: correcto.
- Búsqueda: agrupación de resultados y enlaces internos seguros con cliente simulado: correcta.
- Sistema: parsers de `/proc`, carga defensiva y recolección de métricas: correctos.

## Integración continua

`.github/workflows/ci.yml` instala `requirements-lock.txt`, compila `app` y `tests`, ejecuta la suite, importa `app.main`, analiza todas las plantillas Jinja2 y valida los scripts de despliegue. `NetDoc CI` completó correctamente todas las etapas después de integrar el bloqueo temporal de login; el último commit debe conservar el mismo resultado antes de fusionar.

Estos resultados no validan systemd, el puerto 8101, la base persistente real del servidor, la IP observada detrás de un proxy, el navegador con datos reales ni NetBox.

## Prueba manual requerida en desarrollo

1. Respaldar y confirmar el `DATABASE_URL` de desarrollo.
2. Desplegar únicamente `develop` en el puerto 8101.
3. Iniciar sesión con la cuenta administrativa existente.
4. Crear usuarios de los roles Administrador, Operador y Consulta.
5. Confirmar que cada menú y URL respeta sus permisos, incluyendo Búsqueda y Sistema.
6. Probar creación, edición, activación y cambio de contraseña desde administración.
7. Abrir Mi perfil con cada rol, actualizar nombre/correo y cambiar la contraseña propia.
8. Confirmar que una contraseña actual incorrecta no permite el cambio.
9. Realizar cinco fallos controlados con una cuenta de prueba y confirmar HTTP 429, `Retry-After` y el evento `LOGIN_BLOCKED`.
10. Confirmar que la desactivación y los cambios de rol se aplican sin volver a iniciar sesión.
11. Crear y editar un rol personalizado.
12. Verificar filtros por fecha/recurso y exportar un CSV de Auditoría.
13. Probar Búsqueda con dispositivos, interfaces, racks, sitios y cables reales.
14. Revisar CPU, RAM, disco, red y uptime en Sistema sin acciones de escritura.
15. Confirmar que desarrollo sigue sin escritura hacia NetBox.
16. Revisar logs, permisos del archivo de base y que Git lo ignore.

## Estrategia siguiente

Agregar pruebas de CSRF inválido, protección del último administrador, rangos de fecha, fallos de base, correo de perfil, proxy/IP real, más integración simulada con NetBox y migraciones. Antes de `main`: diff y documentación revisados, pruebas existentes, despliegue en desarrollo, revisión de permisos y validación manual del propietario sin inventar resultados.
