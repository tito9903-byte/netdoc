# Operaciones rutinarias

Ejecute en el servidor solo cuando esté autorizado. Codex no probó estos comandos contra el servidor.

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
```

Actualice con `netdoc-deploy-dev` o `netdoc-deploy-prod` según [DEPLOYMENT](DEPLOYMENT.md); no intercambie directorios ni servicios. Los comandos de despliegue se invocan como root porque controlan systemd, pero todas las operaciones Git, pip y Python internas se ejecutan como `sshtelenord`.

Para rollback manual siga el documento de despliegue. El respaldo `/opt/netbox-documental` solo puede recuperarse mediante un procedimiento formal, sin asumir que esté listo.

Diagnóstico recomendado:

1. Confirme servicio y puerto.
2. Confirme rama y commit usando `runuser -u sshtelenord`.
3. Confirme presencia y permisos de `.env` sin leer su contenido.
4. Revise logs.
5. Compruebe `/login` mediante GET.
6. Confirme que no existan errores evidentes ni escrituras inesperadas.

Escale un incidente si hay exposición de secretos, indisponibilidad persistente, escritura inesperada, rollback fallido, propietarios incorrectos o dudas sobre la integridad del repositorio.