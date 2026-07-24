# Prompt maestro de continuidad de NetDoc

Copia este documento completo en una conversación nueva para continuar el proyecto sin depender de conversaciones anteriores.

## Contexto general

Estás continuando el desarrollo de **NetDoc**, una plataforma web independiente para consultar, crear y visualizar documentación de infraestructura de red. NetBox es la fuente oficial del inventario técnico; NetDoc simplifica la experiencia de uso, aplica formularios guiados y presenta la información de forma operativa.

- Repositorio: `tito9903-byte/netdoc`
- Servidor dedicado de NetDoc: `192.168.10.93`
- NetBox: `https://192.168.10.95`
- Responsable: Luis Emilio García Pichardo
- Sistema operativo del servidor: Ubuntu 24.04
- NetBox documentado: versión 4.4.2

NetDoc es la única aplicación de este proyecto alojada en ese servidor. No inventes integraciones ni relaciones con otros sistemas.

## Entornos

### Desarrollo

- Ruta: `/opt/netdoc-dev`
- Rama: `develop`
- Servicio systemd: `netdoc-dev`
- Puerto: `8101`
- URL: `http://192.168.10.93:8101`
- Cookie de sesión: `netdoc_dev_session`
- Escritura NetBox: debe estar deshabilitada con `NETBOX_WRITE_ENABLED=false`

### Producción

- Ruta: `/opt/netdoc-prod`
- Rama: `main`
- Servicio systemd: `netdoc-prod`
- Puerto: `8100`
- URL: `http://192.168.10.93:8100`
- Escritura NetBox: controlada mediante el `.env` de producción

### Respaldo temporal

- Ruta: `/opt/netbox-documental`
- No es producción activa.
- No debe eliminarse ni reutilizarse sin una decisión operativa explícita.

El propietario verificó manualmente ambos entornos el 2026-07-24 y obtuvo HTTP 200. Esta evidencia manual no sustituye pruebas automatizadas ni significa que Codex haya accedido al servidor.

## Arquitectura y tecnologías

Flujo principal:

`Navegador → FastAPI/Jinja2 → servicios HTTPX → API REST de NetBox`

Tecnologías principales:

- Python
- FastAPI
- Jinja2
- HTTPX
- Pydantic Settings
- SessionMiddleware
- Argon2
- Uvicorn
- HTML, CSS y JavaScript
- systemd
- Git y GitHub

Estructura relevante:

- `app/main.py`: creación de la aplicación, middleware y rutas principales.
- `app/core/`: configuración y seguridad.
- `app/routers/`: rutas web y API.
- `app/services/`: comunicación y transformación de datos de NetBox.
- `app/templates/`: plantillas Jinja2.
- `app/static/`: CSS, JavaScript e imágenes.
- `scripts/`: despliegue controlado.
- `docs/`: documentación viva del proyecto.
- `requirements.txt` y `requirements-lock.txt`: dependencias.
- `.env`: configuración sensible local; nunca se versiona ni se imprime.

## Funcionalidades implementadas

- Inicio de sesión administrativo inicial.
- Dashboard conectado a NetBox.
- Listado de dispositivos.
- Búsqueda, filtros y paginación de dispositivos.
- Vista de detalle de dispositivos.
- Consulta de interfaces.
- Creación guiada de equipos.
- Consulta de conexiones y cables.
- Creación de cables entre interfaces.
- Listado de racks.
- Visualización 2D de racks.
- Selector de detalle e inspector de equipos dentro del rack.
- Integración REST con NetBox.
- Separación de sesiones por entorno.

## Funcionalidades planificadas

Próximo objetivo principal:

- Usuarios.
- Roles.
- Permisos.
- Auditoría.

Después:

- Edición y eliminación controlada.
- Patch panels y puertos frontales/traseros.
- Edición y desconexión de cables.
- Búsqueda global.
- Topologías física y lógica.
- Visualización 3D.
- Pruebas automatizadas.
- Manejo centralizado de errores.
- Observabilidad y métricas.
- Fortalecimiento de seguridad.

## Estado operativo y riesgos

- Producción y desarrollo fueron verificados manualmente con HTTP 200 el 2026-07-24.
- Los scripts `netdoc-deploy-dev` y `netdoc-deploy-prod` están versionados en el repositorio, pero no debe afirmarse que están instalados o probados en el servidor hasta realizar esa validación.
- No existe todavía una suite automatizada de pruebas versionada.
- El token de NetBox debe rotarse porque anteriormente estuvo expuesto en capturas.
- Los permisos de NetBox deben reducirse al mínimo necesario.
- El despliegue debe evitar archivos propiedad de root dentro del repositorio o `.venv`.
- No se debe modificar producción directamente.

## Flujo Git obligatorio

- Crear ramas `feature/*` desde `develop`.
- Abrir pull request hacia `develop`.
- Revisar y probar en desarrollo.
- Solo después promover `develop` hacia `main` mediante otro PR.
- No programar directamente en `main`.
- No fusionar automáticamente.
- Un `git push` no despliega al servidor.

Convenciones:

- Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `ci:`, `build:`, `perf:` y `revert:`.
- Código Python conforme a PEP 8.
- Documentación en español claro y con enlaces relativos.
- Actualizar `CHANGELOG.md`, `docs/PROJECT_STATUS.md` y ADR cuando corresponda.

## Despliegue

Scripts previstos:

- `scripts/netdoc-deploy-dev`
- `scripts/netdoc-deploy-prod`

Instalación esperada:

- `/usr/local/sbin/netdoc-deploy-dev`
- `/usr/local/sbin/netdoc-deploy-prod`

Los scripts deben:

- Ejecutarse como root para controlar systemd.
- Ejecutar Git, pip y Python como `sshtelenord` mediante `runuser`.
- Trabajar solo en su entorno correspondiente.
- Usar `flock` para impedir despliegues simultáneos.
- Verificar rama, remoto, `.env`, `.venv`, dependencias y propietarios.
- Rechazar árboles Git con cambios locales o archivos no rastreados.
- Confirmar que `.env` no esté versionado y sí esté ignorado.
- Instalar `requirements-lock.txt` y usar `requirements.txt` solo como respaldo.
- Compilar e importar `app.main` antes de reiniciar.
- Reiniciar únicamente el servicio correcto.
- Verificar `/login` con GET, aceptando HTTP 200 o cualquier 3xx.
- Reintentar la comprobación durante al menos 30 segundos.
- Restaurar el commit anterior y dependencias si ocurre un fallo.
- Producción debe exigir confirmación `DESPLEGAR` o `--yes`.

## Validaciones obligatorias antes de terminar una tarea

- Revisar el diff completo.
- `python -m compileall app`
- Importar `app.main`.
- `bash -n` en scripts modificados.
- Verificar permisos ejecutables de scripts.
- Revisar enlaces Markdown.
- Buscar secretos, claves privadas, tokens y credenciales.
- Ejecutar pruebas existentes cuando existan.
- Declarar con honestidad qué no pudo probarse.

## Archivos que deben leerse primero

1. `AGENTS.md`
2. `docs/PROJECT_STATUS.md`
3. `docs/ARCHITECTURE.md`
4. `docs/SECURITY.md`
5. `docs/DEPLOYMENT.md`
6. `docs/OPERATIONS.md`
7. `CONTRIBUTING.md`
8. `docs/adr/README.md` y ADR vigentes
9. `CHANGELOG.md`
10. `docs/ROADMAP.md`

## Información que nunca debe inventarse

- Tokens, contraseñas, hashes o claves.
- Contenido de `.env`.
- Acceso al servidor.
- Resultados de despliegues no ejecutados.
- Resultados de pruebas no ejecutadas.
- Versiones no verificadas.
- Funcionalidades no implementadas.
- Permisos exactos de NetBox no confirmados.
- Esquemas o campos de NetBox no observados.
- Servicios, IP, puertos o integraciones no documentados.
- Relaciones con proyectos ajenos a NetDoc.

## Formato esperado de respuesta del agente

En cada tarea responde indicando:

1. Qué entendiste.
2. Qué archivos revisaste.
3. Qué archivos modificaste.
4. Decisiones técnicas tomadas.
5. Validaciones ejecutadas y resultados reales.
6. Limitaciones y elementos no probados.
7. Qué debe probar el propietario.
8. Documentación actualizada.
9. Pendientes y próximo paso.

Una tarea se considera terminada únicamente cuando los cambios están revisados, la documentación es coherente, las validaciones son reales, existe un commit y se abrió o actualizó el PR correcto sin fusionarlo automáticamente.