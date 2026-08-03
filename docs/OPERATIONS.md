# Operaciones rutinarias

Ejecute en el servidor solo cuando esté autorizado. Codex no probó estos comandos contra el servidor.

## Estado de servicios, puertos y repositorios

```bash
systemctl status netdoc-prod
systemctl status netdoc-dev
journalctl -u netdoc-prod -n 100 --no-pager
journalctl -u netdoc-dev -n 100 --no-pager
ss -ltnp | grep -E ':8100|:8101'
curl --silent --show-error --output /dev/null --write-out 'producción HTTP %{http_code}\n' http://127.0.0.1:8100/login
curl --silent --show-error --output /dev/null --write-out 'desarrollo HTTP %{http_code}\n' http://127.0.0.1:8101/login
runuser -u sshtelenord -- git -C /opt/netdoc-prod branch --show-current
runuser -u sshtelenord -- git -C /opt/netdoc-prod rev-parse HEAD
runuser -u sshtelenord -- git -C /opt/netdoc-dev branch --show-current
runuser -u sshtelenord -- git -C /opt/netdoc-dev rev-parse HEAD
systemctl show netdoc-prod --property=MemoryCurrent --property=CPUUsageNSec
systemctl show netdoc-dev --property=MemoryCurrent --property=CPUUsageNSec
stat -c '%a %U:%G %n' /opt/netdoc-prod/.env /opt/netdoc-dev/.env
[[ -f /opt/netdoc-prod/.env ]] && echo '.env de producción presente'
[[ -f /opt/netdoc-dev/.env ]] && echo '.env de desarrollo presente'
runuser -u sshtelenord -- bash -lc 'cd /opt/netdoc-dev && .venv/bin/python -c "from app.core.config import get_settings; print(str(get_settings().netbox_write_enabled).lower())"'
```

Actualice con `netdoc-deploy-dev` o `netdoc-deploy-prod` según [DEPLOYMENT](DEPLOYMENT.md); no intercambie directorios ni servicios. Los comandos de despliegue se invocan como root porque controlan systemd, pero las operaciones Git, pip, Python y Alembic se ejecutan como `sshtelenord`.

## Estado de la base y migraciones

Alembic obtiene `DATABASE_URL` desde el `.env` del entorno, por lo que los comandos deben ejecutarse desde el directorio correspondiente:

```bash
runuser -u sshtelenord -- bash -lc 'cd /opt/netdoc-dev && .venv/bin/alembic current'
runuser -u sshtelenord -- bash -lc 'cd /opt/netdoc-dev && .venv/bin/alembic heads'
runuser -u sshtelenord -- bash -lc 'cd /opt/netdoc-prod && .venv/bin/alembic current'
runuser -u sshtelenord -- bash -lc 'cd /opt/netdoc-prod && .venv/bin/alembic heads'
```

En esta rama la cabeza esperada es `20260724_0001`. `current` debe coincidir con `heads` después del arranque. No ejecute `stamp`, `upgrade`, `downgrade` ni edite `alembic_version` manualmente durante una incidencia sin revisar antes la base y el procedimiento de recuperación.

Para una base SQLite predeterminada, verifique existencia y propietario sin leer datos:

```bash
stat -c '%a %U:%G %s bytes %n' /opt/netdoc-dev/data/netdoc.db
stat -c '%a %U:%G %s bytes %n' /opt/netdoc-prod/data/netdoc.db
find /opt/netdoc-dev/data -maxdepth 1 -type f -name 'netdoc.db.pre-migration-*' -printf '%M %u:%g %s %TY-%Tm-%Td %TH:%TM %p\n'
find /opt/netdoc-prod/data -maxdepth 1 -type f -name 'netdoc.db.pre-migration-*' -printf '%M %u:%g %s %TY-%Tm-%Td %TH:%TM %p\n'
```

Las rutas anteriores solo aplican cuando `DATABASE_URL` usa el valor predeterminado. No copie bases entre desarrollo y producción.

## Diagnóstico recomendado

1. Confirme servicio y puerto.
2. Confirme rama y commit usando `runuser -u sshtelenord`.
3. Confirme presencia y permisos de `.env` sin leer su contenido.
4. Revise `alembic current` y `alembic heads`.
5. Revise logs buscando errores de migración, esquema parcial, SQLite o permisos.
6. Compruebe `/login` mediante GET.
7. Confirme que la base pertenece a `sshtelenord` y que existe un respaldo previo a la migración.
8. Confirme que el modo de escritura coincida con la autorización vigente. Si
   está habilitado, contraste cada operación esperada con NetBox y Auditoría e
   investigue cualquier escritura no reconocida.

Búsqueda rápida de errores relevantes:

```bash
journalctl -u netdoc-dev -n 300 --no-pager | grep -Ei 'alembic|migration|schema|sqlite|database|permission|traceback|error'
journalctl -u netdoc-prod -n 300 --no-pager | grep -Ei 'alembic|migration|schema|sqlite|database|permission|traceback|error'
```

## Recuperación

Para rollback de código siga [DEPLOYMENT](DEPLOYMENT.md). El script no revierte el esquema ni restaura la base. Si la aplicación deja de arrancar después de una migración:

1. Detenga únicamente el servicio afectado.
2. No elimine ni modifique la base fallida.
3. Copie la base fallida con otro nombre para análisis.
4. Verifique el respaldo previo.
5. Restaure el respaldo con propietario `sshtelenord` y permisos restrictivos.
6. Restaure el commit compatible.
7. Inicie el servicio y valide `/login`, `alembic current` y logs.

El respaldo `/opt/netbox-documental` solo puede recuperarse mediante un procedimiento formal; no debe asumirse que contiene la base nueva ni que está listo para sustituir producción.

Escale un incidente si hay exposición de secretos, indisponibilidad persistente, escritura inesperada, migración o rollback fallido, esquema parcial, propietarios incorrectos, pérdida de respaldo o dudas sobre la integridad del repositorio o la base.
