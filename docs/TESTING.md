# Pruebas

## Estado actual

El repositorio incluye pruebas de servicios de acceso, rutas administrativas, búsqueda, sistema, perfil, protección de login y migraciones en `tests/`. Las validaciones generales incluyen compilación, grafo Alembic, importación de `app.main`, sintaxis Bash, revisión de plantillas y pruebas manuales en desarrollo. Las pruebas HTTP contra los puertos del servidor deben ejecutarse únicamente en el servidor autorizado.

| Módulo | Cobertura actual | Pendiente |
|---|---|---|
| Autenticación y roles | Inicialización, usuario, contraseña, permisos, persistencia, actualización inmediata y bloqueo temporal | concurrencia y rate limiting distribuido |
| Usuarios administrativos | Login, acceso, denegación, desactivación, cambio de rol y eliminación de otra cuenta | último administrador, autoeliminación y CSRF inválido |
| Perfil | Acceso, actualización de datos, verificación de contraseña actual y cambio de contraseña | correo inválido, CSRF inválido y sesión concurrente |
| Auditoría | Creación, login fallido, login bloqueado y exportación CSV | fechas extremas, retención y carga |
| Búsqueda global | Agrupación, enlaces seguros y consulta corta | integración real con filtros `q` de NetBox |
| Sistema | Parsers de memoria/red, carga y métricas seguras | valores de servidor real, umbrales y compatibilidad no Linux |
| Migraciones | base vacía, esquema heredado completo, idempotencia y esquema parcial | respaldo/restauración y próxima revisión incremental |
| Dispositivos/interfaces | Filtros vacíos, navegación interna y agrupación de IPv4/IPv6 por interfaz | integración real con NetBox y datos de borde del catálogo |
| Direccionamiento IP | Lectura, capacidad, filtros, carga diferida y alta protegida de pools | integración real con jerarquía y token limitado |
| Creación/cables | Validación manual existente | autorización, CSRF, errores y regresión |
| Racks | Manual | datos de borde y UI |
| Despliegue | Sintaxis y ejecución manual conocida | ensayo del nuevo esquema y respaldo |

## Comandos

```bash
scripts/netdoc-test-isolated tests.test_sites tests.test_access_control
scripts/netdoc-test-isolated tests.test_ipam_pool_management
scripts/netdoc-test-isolated
python -c 'from app.main import app; print(app.title, len(app.routes))'
bash -n scripts/netdoc-deploy-dev
bash -n scripts/netdoc-deploy-prod
```

El primer comando ejecuta una selección dentro de un entorno desechable; el
segundo ejecuta toda la suite. El script establece un `DATABASE_URL` temporal,
valores de prueba y escritura hacia NetBox deshabilitada antes de importar la
aplicación.

No ejecute `python -m unittest` directamente desde un checkout que contenga el
`.env` de desarrollo o producción. Las configuraciones de FastAPI se resuelven
al importar la aplicación y una ejecución directa puede abrir la base real,
crear eventos de auditoría o autenticar contra usuarios reales. Una prueba
selectiva debe pasar sus módulos como argumentos a
`scripts/netdoc-test-isolated`.

## Resultados de la rama `feature/access-control-audit`

Se ejecutaron en un entorno aislado, no en el servidor:

- Compilación de `app`, `tests` y `migrations`: correcta.
- Grafo Alembic: una sola cabeza `20260724_0001`.
- Migración de una base vacía: correcta.
- Segunda ejecución sobre una base versionada: idempotente.
- Adopción de una base heredada completa mediante `stamp`: correcta.
- Rechazo de una base con esquema parcial: correcto.
- Inicialización de SQLite en memoria y archivo temporal: correcta.
- Creación de 11 permisos y tres roles iniciales: correcta.
- Creación y autenticación de usuarios de prueba: correcta.
- Rechazo de contraseña débil: correcto.
- Creación de rol personalizado y evento de auditoría: correcta.
- Persistencia de permisos personalizados del rol Operador tras repetir la inicialización: correcta.
- Carga sintáctica de 19 plantillas: correcta.
- Importación de la aplicación con 41 rutas: correcta.
- 27 pruebas automatizadas: superadas localmente y por GitHub Actions.
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

`.github/workflows/ci.yml` instala `requirements-lock.txt`, compila `app`, `tests` y `migrations`, valida `alembic heads`, ejecuta la suite, importa `app.main`, analiza todas las plantillas Jinja2 y valida los scripts de despliegue. `NetDoc CI` completó correctamente cada etapa para la revisión inicial Alembic.

Estos resultados no validan systemd, el endpoint real de desarrollo, una base
persistente del servidor, la restauración de un respaldo, la dirección
observada detrás de un proxy, el navegador con datos reales ni NetBox.

## Prueba manual requerida en desarrollo

1. Confirmar el `DATABASE_URL` de desarrollo sin mostrar credenciales.
2. Respaldar la base existente y comprobar tamaño, propietario y permisos del respaldo.
3. Confirmar `alembic heads` y una sola cabeza.
4. Desplegar únicamente `develop` en el endpoint aislado de desarrollo.
5. Revisar logs del arranque y confirmar que la base fue creada, marcada o actualizada sin pérdida.
6. Iniciar sesión con la cuenta administrativa existente.
7. Crear usuarios de los roles Administrador, Operador y Consulta.
8. Confirmar que cada menú y URL respeta sus permisos, incluyendo Búsqueda y Sistema.
9. Probar creación, edición, activación y cambio de contraseña desde administración.
10. Abrir Mi perfil con cada rol, actualizar nombre/correo y cambiar la contraseña propia.
11. Confirmar que una contraseña actual incorrecta no permite el cambio.
12. Realizar cinco fallos controlados con una cuenta de prueba y confirmar HTTP 429, `Retry-After` y el evento `LOGIN_BLOCKED`.
13. Confirmar que la desactivación y los cambios de rol se aplican sin volver a iniciar sesión.
14. Crear y editar un rol personalizado.
15. Verificar filtros por fecha/recurso y exportar un CSV de Auditoría.
16. Probar Búsqueda con dispositivos, interfaces, racks, sitios y cables reales.
17. Revisar CPU, RAM, disco, red y uptime en Sistema sin acciones de escritura.
18. Confirmar que desarrollo sigue sin escritura hacia NetBox.
19. Revisar logs, permisos del archivo de base y que Git lo ignore.

## Estrategia siguiente

Agregar pruebas de CSRF inválido, protección del último administrador, rangos de fecha, fallos de base, correo de perfil, proxy/IP real, respaldo/restauración y una segunda revisión Alembic de prueba. Antes de `main`: diff y documentación revisados, pruebas existentes, despliegue en desarrollo, revisión de permisos y validación manual del propietario sin inventar resultados.
