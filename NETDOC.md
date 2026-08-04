# NetDoc: documento maestro de continuidad

Este es el punto de entrada obligatorio para continuar NetDoc en cualquier
chat. El agente debe leerlo completo junto con `AGENTS.md`, pero antes de actuar
tiene que comprobar el estado real del repositorio y de GitHub.

## Regla de actualización

`NETDOC.md` se actualiza después de que el propietario confirme que el cambio
funciona en desarrollo. Debe registrar el resultado realmente validado, PR,
SHA, pruebas, estado de desarrollo, estado de producción y pendientes. Una
implementación, un CI correcto o un HTTP 200 no sustituyen esa validación
funcional y no autorizan a describir el cambio como terminado.

La actualización de este documento sigue el mismo flujo de revisión por rama y
PR. Producción solo se actualiza con una autorización explícita y separada.

## Contexto general

Estás continuando el desarrollo de **NetDoc**, una plataforma web independiente
para consultar, crear y visualizar documentación de infraestructura de red.
NetBox es la fuente oficial del inventario técnico; NetDoc simplifica la
experiencia operativa y mantiene únicamente los datos propios de la aplicación.

- Repositorio: `tito9903-byte/netdoc`
- Responsable: Luis Emilio García Pichardo
- Servidor dedicado: `192.168.10.93`
- Sistema operativo: Ubuntu 24.04
- NetBox: `https://192.168.10.95`
- Versión de NetBox documentada: 4.4.2
- Versión de aplicación documentada: 0.10.1

No inventes acceso al servidor, integraciones, datos de NetBox ni resultados de
pruebas o despliegues.

## Fuentes de verdad

Antes de modificar archivos:

1. Comprueba ruta, rama, `git status`, remotos y últimos commits.
2. Lee `AGENTS.md` completo.
3. Lee `docs/PROJECT_STATUS.md`, `docs/ARCHITECTURE.md`,
   `docs/SECURITY.md`, `docs/TESTING.md`, `docs/DEPLOYMENT.md`,
   `docs/OPERATIONS.md`, `CONTRIBUTING.md`, `CHANGELOG.md` y los ADR vigentes.
4. Inspecciona el código y las pruebas del módulo afectado.
5. Confirma en GitHub la rama y el PR cuando la tarea dependa de estado remoto.

El código versionado define el comportamiento. `PROJECT_STATUS.md` define el
estado y las prioridades. Los ADR conservan decisiones de arquitectura. GitHub
es la fuente del código compartido; un commit exclusivamente local no está
publicado.

## Estado validado al 2026-08-04

- `main`: producción 0.10.0 en
  `bb8a63af37dfdadeba8f40910de50212d0b09774`.
- `develop`: integración 0.10.1 en
  `45f8a300f35f833cde353923edc0f0c931571400`.
- PR #13: Sites, integrado en `develop`.
- PR #14: navegación contextual sin `Acciones rápidas`, integrado en
  `develop`.
- PR #15: restauración del detalle profesional del rack, integrado en
  `develop`.
- PR #16: documento maestro `NETDOC.md` y reglas persistentes de continuidad,
  integrado en `develop`.
- PR #17: funcionamiento de **Detalle ampliado** y optimización del catálogo de
  racks, integrado en `develop`.
- PR #27: direcciones IPv4 e IPv6 por interfaz en la ficha del dispositivo,
  integrado en `develop`.
- Desarrollo está desplegado en
  `45f8a300f35f833cde353923edc0f0c931571400`; el servicio quedó activo, el
  puerto 8101 respondió correctamente y Alembic permaneció en
  `20260725_0002`.
- La corrección del PR #17 superó 16/16 pruebas específicas de racks, 104/104
  pruebas en la suite aislada completa y `NetDoc CI`; el comportamiento
  JavaScript también se comprobó con Node.
- El propietario confirmó en desarrollo que el catálogo de Racks carga con
  agilidad, que el rack abre y que el selector **Rack completo / Detalle
  ampliado** funciona.
- El propietario confirmó que la restauración del rack funciona en desarrollo:
  inventario, búsqueda, acceso a la ficha y reporte PDF.
- Las posiciones y alturas U se conservaron; las fotografías usan
  `width: 100%`, `height: 100%` y `object-fit: fill`.
- La corrección del PR #27 superó 4/4 pruebas específicas, 138/138 pruebas en
  la suite aislada completa y `NetDoc CI`.
- El propietario confirmó con inventario real en desarrollo que la columna
  **Direcciones IP** muestra las IP asignadas a las interfaces del dispositivo.
  La IP principal permanece como un dato independiente configurado en NetBox.
- Producción permanece en `bb8a63af37dfdadeba8f40910de50212d0b09774` y no
  fue modificada por este despliegue.
- Sigue pendiente completar la validación funcional de Sites y de los permisos
  por rol.

Estos datos son un punto de partida, no una autorización para asumir que siguen
vigentes. Verifica GitHub y el checkout antes de continuar.

## Regla de producto para navegación

- La barra lateral lleva a módulos.
- Cada creación, edición o retiro comienza dentro del catálogo o detalle del
  módulo responsable.
- No debe existir un módulo global de `Acciones rápidas`.
- No dupliques en la barra lateral enlaces como Crear equipo, Crear rack o
  Crear site.
- Eliminar un acceso duplicado nunca implica eliminar la ruta, el permiso, la
  validación, el formulario ni la auditoría de la operación.
- Esta regla se aplica a Dispositivos, Fabricantes, Modelos, Plantillas,
  Direccionamiento IP, Conexiones, Racks, Sites y módulos futuros.

## Entornos

### Desarrollo

- Ruta: `/opt/netdoc-dev`
- Rama estable: `develop`
- Servicio: `netdoc-dev`
- Puerto: `8101`
- URL: `http://192.168.10.93:8101`
- Cookie: `netdoc_dev_session`
- Escritura NetBox: `NETBOX_WRITE_ENABLED=false`
- Script: `/usr/local/sbin/netdoc-deploy-dev`

### Producción

- Ruta: `/opt/netdoc-prod`
- Rama: `main`
- Servicio: `netdoc-prod`
- Puerto: `8100`
- URL: `http://192.168.10.93:8100`
- Escritura NetBox: controlada mediante `.env`
- Script: `/usr/local/sbin/netdoc-deploy-prod`

### Respaldo temporal

- Ruta: `/opt/netbox-documental`
- No es producción activa.
- No debe eliminarse ni reutilizarse sin decisión operativa explícita.

Los checkouts del servidor son destinos de despliegue. No desarrolles, crees
commits, apliques parches, reconstruyas historial ni publiques ramas desde
ellos.

## Flujo obligatorio para cada módulo o cambio

Este es el proceso normal de trabajo, tanto para módulos nuevos como para
correcciones:

1. Inspeccionar el repositorio, la documentación, el código afectado y el estado
   remoto.
2. Actualizar la referencia de `develop` y crear una rama `feature/<tema>`,
   `fix/<tema>` o `refactor/<tema>` desde el SHA correcto.
3. Implementar una sola tarea coherente sin mezclar cambios ajenos ni
   `deliverables/`.
4. Añadir o actualizar pruebas específicas que demuestren el comportamiento y
   protejan la regresión.
5. Ejecutar primero la selección aplicable mediante
   `scripts/netdoc-test-isolated <módulos>`.
6. Ejecutar después la suite completa con `scripts/netdoc-test-isolated`.
7. Ejecutar las validaciones aplicables: compilación Python, una sola cabeza
   Alembic, importación de `app.main`, carga de plantillas Jinja2, sintaxis Bash,
   enlaces Markdown, diff completo y búsqueda de secretos.
8. Actualizar `docs/PROJECT_STATUS.md`, `CHANGELOG.md` y la documentación
   afectada. Crear un ADR únicamente cuando cambie arquitectura o una decisión
   persistente que lo requiera.
9. Crear un commit con Conventional Commits incluyendo solo los archivos de la
   tarea.
10. Publicar la rama por una vía autenticada, confirmar el SHA remoto y abrir o
    actualizar un PR hacia `develop`. No fusionar automáticamente.
11. Verificar el CI y detenerse si falla.
12. Fusionar hacia `develop` solamente con autorización del propietario y
    bloqueando la operación al SHA revisado.
13. Desplegar desarrollo únicamente con autorización, consumiendo el SHA remoto
    verificado. Validar solo `/opt/netdoc-dev`, `netdoc-dev` y 8101.
14. Solicitar revisión funcional o visual del propietario en desarrollo.
15. Corregir cualquier incidencia repitiendo el flujo desde una rama; un fallo
    en desarrollo impide avanzar.
16. Promover `develop` hacia `main` y desplegar 8100 solamente después de una
    autorización explícita y separada para producción.

Flujo resumido:

`inspeccionar → rama → implementar → pruebas específicas → suite completa → documentación → commit → publicar → verificar SHA → PR → CI → autorización → develop → revisión → autorización separada → main/producción`

No entregues como procedimiento normal fragmentos para que el propietario los
copie al repositorio. Si autorizó una implementación y existe acceso al código,
el agente debe editar, probar, confirmar y publicar. Los bloques manuales se
reservan para operaciones de servidor autorizadas o bloqueos reales.

## Pruebas obligatorias

Usa siempre el ejecutor aislado:

```bash
scripts/netdoc-test-isolated tests.test_sites tests.test_access_control
scripts/netdoc-test-isolated
python -m compileall -q app tests migrations
.venv/bin/alembic heads
python -c 'from app.main import app; print(app.title, len(app.routes))'
bash -n scripts/netdoc-deploy-dev
bash -n scripts/netdoc-deploy-prod
```

Ajusta la selección del primer comando al módulo modificado. No ejecutes
`python -m unittest` directamente en un checkout que contenga `.env`: la
importación puede cargar la base y las credenciales reales del entorno. El
ejecutor aislado establece base temporal, credenciales desechables y escritura
hacia NetBox deshabilitada.

Nunca afirmes que una prueba pasó sin conservar la salida o evidencia
verificable. CI no sustituye la revisión funcional del navegador ni las pruebas
contra el servidor real.

## Arquitectura y límites

Flujo de inventario:

`Navegador → FastAPI/Jinja2 → servicios HTTPX → API REST de NetBox`

Flujo interno:

`FastAPI → SQLAlchemy/Alembic → base propia de NetDoc`

NetBox conserva dispositivos, interfaces, fabricantes, modelos, racks, sites,
cables, IPAM y demás inventario técnico. La base de NetDoc conserva:

- usuarios, roles y permisos;
- relaciones rol-permiso;
- auditoría;
- imágenes frontal y trasera asociadas a modelos de NetBox;
- revisión Alembic aplicada.

No dupliques el inventario principal ni escribas directamente en la base de
NetBox. Las operaciones de inventario usan la API REST y exigen autenticación,
permiso, CSRF y `NETBOX_WRITE_ENABLED=true`.

La cabeza Alembic documentada es `20260725_0002`. Una base vacía recibe todas
las migraciones; una base versionada avanza hasta `head`; una base heredada
completa se marca en `20260724_0001` y recibe revisiones posteriores; un esquema
parcial debe detener el arranque.

Cada entorno usa su propia `DATABASE_URL`. El rollback de código no revierte
migraciones ni restaura la base. Antes de una migración real se requiere un
respaldo verificable.

## Funcionalidad disponible

- Dashboard, búsqueda global y perfil.
- Dispositivos, interfaces y creación guiada.
- Fabricantes, modelos, imágenes y plantillas de puertos.
- Direccionamiento IP.
- Conexiones y cables.
- Racks con catálogo, creación, vistas 2D/3D y ocupación física.
- Sites con catálogo, creación, edición y retiro controlado.
- Usuarios, roles, permisos y auditoría.
- Sistema de solo lectura.
- Planes de cambio seguros y vista previa de cables.

`main` y `develop` pueden diferir. Verifica el árbol de cada rama antes de
afirmar que una función está en producción.

## Seguridad y veracidad

- Nunca leas, imprimas, publiques ni incluyas `.env`, tokens, contraseñas,
  hashes, claves, cookies, certificados o bases.
- No uses `force-push`, no reescribas historial compartido y no elimines cambios
  ajenos para limpiar el árbol.
- No incluyas `deliverables/` ni artefactos temporales en commits.
- La seguridad real vive en el servidor; ocultar un enlace no sustituye
  permisos.
- Desarrollo debe conservar la escritura hacia NetBox deshabilitada.
- No uses el servidor como origen de GitHub.
- Distingue siempre: archivo modificado, commit local, commit remoto, PR, merge,
  despliegue en desarrollo y despliegue en producción.
- Si una prueba, migración, publicación, reinicio o health check falla,
  detente, restaura cuando corresponda y reporta la causa exacta.

## Despliegue

`netdoc-deploy-dev` consume `origin/develop` y reinicia únicamente
`netdoc-dev`. `netdoc-deploy-prod` consume `origin/main`, reinicia únicamente
`netdoc-prod` y exige confirmación explícita.

Antes de desplegar:

- verificar el SHA remoto autorizado;
- confirmar árbol Git limpio;
- identificar `DATABASE_URL` sin mostrarla;
- respaldar la base si hay migraciones o cambios persistentes;
- confirmar una sola cabeza Alembic;
- mantener separados directorios, bases, servicios y puertos.

Después de desplegar:

- confirmar rama y SHA;
- confirmar servicio activo y PID nuevo;
- confirmar directorio de trabajo correcto;
- comprobar `/login` con HTTP 200 o 3xx;
- revisar logs y migraciones;
- realizar la validación funcional solicitada.

Producción nunca se modifica por implicación. Requiere autorización explícita
después de la revisión de desarrollo.

## Pendientes conocidos

- Completar la validación funcional de Sites en desarrollo.
- Confirmar permisos `sites.view` y `sites.manage` con los tres roles.
- Validar creación, edición, retiro y eventos de auditoría de Sites.
- Confirmar filtros de racks por site.
- Definir almacenamiento y respaldo para una imagen representativa de cada
  site antes de implementarla.
- Mantener en seguimiento respaldo/restauración, retención de auditoría,
  SQLite antes de múltiples workers y módulos físicos pendientes.

## Formato esperado de entrega

Al terminar informa:

- resultado real;
- rama;
- SHA local;
- SHA remoto si fue publicado;
- archivos modificados;
- pruebas ejecutadas;
- PR y CI;
- entorno afectado;
- validación manual pendiente.

Responde en español, directo y con evidencia. No ocultes errores ni afirmes
éxito sin verificación.

## Instrucción breve para un chat nuevo

El propietario puede iniciar la continuidad con:

> Ve al repositorio `tito9903-byte/netdoc` en GitHub. Lee completamente
> `NETDOC.md` y `AGENTS.md`, verifica el estado real del repositorio y explícame
> dónde quedó el proyecto. No modifiques, fusiones ni despliegues nada hasta que
> te autorice el siguiente cambio.
