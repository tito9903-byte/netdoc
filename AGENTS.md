# Instrucciones para agentes

Estas reglas son obligatorias para cualquier agente o chat que trabaje en
NetDoc. No dependa de la memoria de conversaciones anteriores: confirme siempre
el estado real del repositorio y use la documentación versionada.

## Fuentes de verdad

Antes de cambiar archivos, lea `docs/PROJECT_STATUS.md`,
`docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/TESTING.md`,
`docs/DEPLOYMENT.md`, `docs/OPERATIONS.md`, `CONTRIBUTING.md`,
`CHANGELOG.md` y los ADR vigentes.

- El código versionado define el comportamiento real.
- `docs/PROJECT_STATUS.md` define el estado, la rama activa y las prioridades.
- Los ADR definen las decisiones de arquitectura aceptadas.
- NetBox es la fuente oficial del inventario técnico.
- GitHub es la fuente oficial del código compartido. Un commit que existe solo
  en un checkout local todavía no está publicado.

## Principios de producto y navegación

- La navegación principal lleva a módulos, no duplica operaciones.
- Toda acción de crear, editar o retirar comienza dentro del catálogo o detalle
  del módulo correspondiente.
- No agregue un bloque global de `Acciones rápidas` ni enlaces de creación
  paralelos en la barra lateral. Dispositivos, modelos, racks, sites y los
  módulos futuros deben conservar su propia entrada contextual.

## Flujo de trabajo obligatorio

1. Antes de actuar, compruebe la ruta del repositorio, la rama, `git status`,
   los remotos y los últimos commits. Preserve cualquier cambio ajeno o no
   publicado; nunca lo descarte, sobrescriba ni mezcle silenciosamente.
2. Para trabajo independiente, actualice `develop` y cree `feature/<tema>` o
   `fix/<tema>`. No programe directamente en `main`.
3. Mantenga una sola tarea activa hasta que sus cambios estén probados,
   confirmados y publicados. No recomiende abrir otro chat para recuperar un
   commit local: primero debe publicarse o transferirse de forma verificable.
4. Cuando el usuario autorice una implementación, el agente debe editar los
   archivos, ejecutar las pruebas y crear el commit. No se limite a entregar
   fragmentos para copiar salvo que el usuario lo pida o exista un bloqueo real.
5. Revise el diff completo, ejecute la prueba específica mediante
   `scripts/netdoc-test-isolated <módulos>` y después la suite aislada completa
   con `scripts/netdoc-test-isolated`. Nunca ejecute `python -m unittest`
   directamente desde un checkout que contenga `.env`: puede cargar la base y
   los secretos del entorno en lugar de los valores desechables de prueba.
   Ejecute además las validaciones aplicables de compilación, Alembic,
   plantillas y sintaxis Bash.
6. Actualice `docs/PROJECT_STATUS.md`, `CHANGELOG.md` y la documentación
   afectada. Cree un ADR si cambia una decisión arquitectónica.
7. Use Conventional Commits y confirme únicamente los archivos de la tarea.
   No incluya artefactos temporales, paquetes de transferencia ni cambios
   ajenos.
8. Publique la rama mediante una vía autenticada disponible: remoto Git
   configurado o conector de GitHub. `gh` facilita operaciones de GitHub, pero
   su ausencia no impide por sí sola crear commits ni necesariamente hacer
   `git push`. Si la publicación falla, informe el error y la credencial o
   permiso exacto que falta; no invente el bloqueo.
9. El servidor de despliegue consume código publicado; no es una estación de
   desarrollo ni el origen de GitHub. No reconstruya commits allí mediante
   `git am`, parches o bloques Base64 y no ejecute `git push` desde el servidor.
   Debe obtener mediante `git fetch` una rama remota y un SHA ya verificados.
10. Después de publicar, verifique que la rama remota apunta al SHA esperado y
    abra o actualice un pull request hacia `develop`. No fusione
    automáticamente.
11. Solo despliegue desarrollo tras autorización del usuario y después de
    verificar el SHA remoto. Valide únicamente `/opt/netdoc-dev`, el servicio
    `netdoc-dev` y el puerto `8101`; luego solicite revisión funcional o visual.
12. Si una prueba, migración, reinicio o health check falla, detenga el flujo,
    restaure el checkout y el servicio anterior cuando corresponda y reporte la
    causa exacta. Un fallo en desarrollo nunca autoriza continuar a producción.
13. Producción requiere autorización explícita posterior a la validación en
    desarrollo y el flujo `develop` hacia `main`. Nunca modifique
    `/opt/netdoc-prod`, `netdoc-prod`, el puerto `8100` ni `main` por
    implicación.

Flujo resumido:

`modificar → probar aislado → commit → publicar rama → verificar SHA remoto → PR a develop → desplegar desde remoto en desarrollo → revisión → producción solo con autorización`

## Seguridad y veracidad

- No incluya ni imprima secretos, `.env`, tokens, contraseñas, hashes, claves,
  cookies o certificados.
- No use `force-push`, no reescriba historial compartido y no elimine cambios
  para limpiar el árbol.
- No afirme que una prueba pasó, una rama fue publicada, un PR fue creado, un
  servicio fue reiniciado o un despliegue terminó sin evidencia verificable.
- Distinga siempre entre cambio de archivos, commit local, commit remoto, PR,
  despliegue en desarrollo y despliegue en producción.
- No invente acceso a servidores, integraciones, funciones ni datos de NetBox.
- Mantenga separadas las responsabilidades entre configuración, seguridad,
  routers, servicios, plantillas, estáticos, scripts y documentación.
- Mantenga la documentación en español y los enlaces internos relativos.
- Los scripts de un entorno nunca deben alterar el otro entorno.

## Entrega

Informe al finalizar: rama, SHA local, SHA remoto si fue publicado, archivos
modificados, pruebas ejecutadas, estado del PR, entorno afectado y cualquier
validación pendiente. Si el usuario debe ejecutar un procedimiento manual,
entregue un script o bloque completo, seguro y listo para copiar.
