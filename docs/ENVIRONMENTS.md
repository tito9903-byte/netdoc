# Desarrollo y producción

## Producción

- Rama: main
- Ruta prevista: /opt/netdoc-prod
- Puerto: 8100
- Servicio: netdoc-prod.service
- Escritura en NetBox: controlada por su `.env`; no modificada en el despliegue
  de desarrollo del 2026-08-03

## Desarrollo

- Rama: develop
- Ruta prevista: /opt/netdoc-dev
- Puerto: 8101
- Servicio: netdoc-dev.service
- Escritura en NetBox: deshabilitada por defecto; habilitada por autorización
  expresa desde 2026-08-03 para validación funcional controlada

Cada entorno tendrá su propia carpeta, entorno virtual, archivo .env,
clave de sesión, servicio systemd y registros.

## Cookies de sesión

Cada entorno debe usar un nombre de cookie distinto:

- Producción: `netdoc_prod_session`
- Desarrollo: `netdoc_dev_session`

Esto evita que una sesión de un entorno sobrescriba la del otro.
