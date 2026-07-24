# Seguridad

- Los archivos .env no se almacenan en Git.
- Los tokens de NetBox deben limitarse por usuario, permisos e IP.
- Producción no debe modificarse manualmente.
- El servidor de producción debe usar acceso Git de solo lectura después
  de la carga inicial.
- Desarrollo debe escribir únicamente en un NetBox de laboratorio o en
  objetos de prueba estrictamente limitados.
