# Desarrollo y producción

## Producción

- Rama: main
- Ruta prevista: /opt/netdoc-prod
- Puerto: 8100
- Servicio: netdoc-prod.service
- Escritura en NetBox: habilitada de forma controlada

## Desarrollo

- Rama: develop
- Ruta prevista: /opt/netdoc-dev
- Puerto: 8101
- Servicio: netdoc-dev.service
- Escritura en NetBox: deshabilitada por defecto

Cada entorno tendrá su propia carpeta, entorno virtual, archivo .env,
clave de sesión, servicio systemd y registros.
