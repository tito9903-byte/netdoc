# Operaciones rutinarias

Ejecute en el servidor solo cuando esté autorizado; estos comandos no se
probaron desde este repositorio.

```bash
systemctl status netdoc-prod; systemctl status netdoc-dev
systemctl restart netdoc-prod; systemctl restart netdoc-dev
journalctl -u netdoc-prod -n 100 --no-pager
journalctl -u netdoc-dev -n 100 --no-pager
ss -ltnp | rg ':8100|:8101'
curl -I http://127.0.0.1:8100/login
curl -I http://127.0.0.1:8101/login
cd /opt/netdoc-prod && git branch --show-current && git rev-parse HEAD
cd /opt/netdoc-dev && git branch --show-current && git rev-parse HEAD
systemctl show netdoc-prod --property=MemoryCurrent --property=CPUUsageNSec
stat -c '%a %U:%G %n' /opt/netdoc-prod/.env /opt/netdoc-dev/.env
[[ -f /opt/netdoc-prod/.env ]] && echo '.env de producción presente'
```

Actualice con `netdoc-deploy-dev` o `netdoc-deploy-prod` según
[DEPLOYMENT](DEPLOYMENT.md); no intercambie directorios ni servicios. Para
rollback manual siga ese documento. El respaldo `/opt/netbox-documental` solo
puede recuperarse temporalmente mediante un procedimiento formal, sin asumir
que esté listo.

Diagnóstico: confirme servicio, puerto, commit, `.env` (sin leerlo), logs,
permisos y respuesta. Escale un incidente si hay exposición de secreto,
indisponibilidad persistente, escrituras inesperadas, rollback fallido o duda
sobre integridad. Tras despliegue: confirme rama/commit, servicio, `/login`,
logs y ausencia de errores evidentes.
