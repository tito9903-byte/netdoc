# Pruebas

## Estrategia

NetDoc utiliza dos niveles distintos de validación:

1. **Suite automatizada aislada:** base temporal, credenciales de prueba, URL de NetBox inválida y `NETBOX_WRITE_ENABLED=false` forzado antes de importar la aplicación.
2. **Prueba manual en desarrollo:** puerto 8101, base propia de desarrollo y escritura controlada habilitada cuando sea necesaria para comprobar creaciones, ediciones, imágenes, racks y cables reales.

Nunca se debe ejecutar la suite automatizada heredando directamente el `.env` de desarrollo o producción.

## Cobertura actual

| Módulo | Cobertura actual | Pendiente |
|---|---|---|
| Autenticación y roles | Inicialización, usuario, contraseña, permisos, persistencia, actualización inmediata y bloqueo temporal | concurrencia y rate limiting distribuido |
| Usuarios administrativos | Login, acceso, denegación, desactivación, cambio de rol y eliminación de otra cuenta | último administrador y autoeliminación |
| Perfil | Acceso, actualización de datos, verificación de contraseña actual y cambio de contraseña | sesión concurrente |
| Auditoría | Creación, login fallido, login bloqueado y exportación CSV | retención y carga |
| Búsqueda global | Agrupación, enlaces seguros y consulta corta | integración exhaustiva con plugins |
| Sistema | Parsers de memoria/red, carga y métricas seguras | compatibilidad no Linux |
| Migraciones | base vacía, esquema heredado completo, idempotencia, esquema parcial y revisión incremental `0002` | ensayo formal de restauración |
| Dispositivos/interfaces | rutas principales y validación manual | integración más amplia con NetBox simulado |
| Creación/cables | plan, validaciones y pruebas manuales | ejecución conversacional confirmada |
| Imágenes de modelos | persistencia, sustitución, firma, MIME, ETag y ruta autenticada | carga elevada y limpieza de huérfanos |
| Racks | alturas, media unidad, 0U, caras, conflictos, imágenes e inspector | accesibilidad y navegador móvil real |
| Reporte PDF | estructura PDF, ruta autenticada, descarga y nombre de archivo | inspección visual en varios lectores PDF |
| Despliegue | sintaxis y ejecución manual conocida | ensayo completo de respaldo/restauración |

## Comando recomendado

```bash
bash scripts/netdoc-test-isolated
```

El script prepara un entorno temporal y luego ejecuta, entre otras validaciones:

```bash
python -m compileall app tests migrations
alembic heads
python -m unittest discover -s tests -v
python -c 'from app.main import app; print(app.title, len(app.routes))'
bash -n scripts/netdoc-deploy-dev
bash -n scripts/netdoc-deploy-prod
```

## Integración continua

`.github/workflows/ci.yml` instala `requirements-lock.txt`, compila `app`, `tests` y `migrations`, valida `alembic heads`, ejecuta la suite, importa `app.main`, analiza todas las plantillas Jinja2 y valida los scripts de despliegue.

CI no valida:

- systemd;
- los puertos 8100/8101;
- el navegador con datos reales;
- permisos reales del token de NetBox;
- restauración de respaldos;
- apariencia visual exacta del rack o del PDF en el equipo del usuario.

## Pruebas de racks y reportes

Las pruebas automatizadas deben confirmar:

- `u_height` completo y fraccionario;
- equipos de 0U;
- posición frontal y trasera;
- profundidad completa;
- conflictos de ocupación;
- rutas autenticadas de fotografías;
- creación del PDF con encabezado `%PDF-1.4` y tabla de referencias;
- respuesta `application/pdf` y `Content-Disposition` de descarga;
- inclusión de equipos posicionados, de 0U y sin posición válida.

La inspección visual del PDF continúa siendo manual. Debe abrirse el archivo descargado, revisar todas las páginas y confirmar que no existen columnas cortadas o textos superpuestos.

## Prueba manual requerida en desarrollo

1. Confirmar el `DATABASE_URL` de desarrollo sin mostrar credenciales.
2. Respaldar la base existente y comprobar tamaño, propietario y permisos.
3. Confirmar `alembic current` y `alembic heads` en `20260725_0002`.
4. Desplegar la rama o `develop` únicamente en el puerto 8101.
5. Revisar logs del arranque y confirmar que no hubo pérdida de datos.
6. Confirmar que `NETBOX_WRITE_ENABLED=true` cuando la prueba requiera modificar NetBox.
7. Crear o editar un objeto de prueba autorizado y verificar auditoría.
8. Abrir un modelo existente, agregar una imagen frontal y reemplazarla.
9. Confirmar que la nueva imagen cambia al recargar y que la otra cara permanece intacta.
10. Revisar el mismo modelo en catálogo, ficha y rack 2D.
11. Abrir un rack de 42U en 3D y comparar **Ajustar** con **Detalle**.
12. Revisar equipos de 1U, 2U y chasis altos, frente y parte trasera.
13. Confirmar que el inspector lateral responde también en 3D.
14. Comprobar que `/topology` redirige al catálogo y que no existe un selector 3D global.
15. Descargar el reporte PDF de ambas caras.
16. Revisar resumen, elevación, inventario, paginación, seriales y etiquetas de activo.
17. Probar un usuario sin `racks.view` y confirmar que no descarga el reporte.
18. Revisar auditoría, logs y permisos de la base local.
19. Confirmar que producción permanece en su commit anterior.

## Regla de seguridad de la suite

`tests/test_000_environment.py` asigna directamente, no con `setdefault`:

```text
DATABASE_URL=<archivo temporal>
NETBOX_URL=https://netbox.invalid
NETBOX_WRITE_ENABLED=false
```

Por tanto, habilitar escritura en el `.env` manual de desarrollo no cambia el comportamiento de la suite aislada. Esta separación es obligatoria y debe mantenerse en futuras pruebas.

## Criterio antes de producción

Antes de abrir o fusionar una promoción hacia `main` se exige:

- CI correcto;
- una sola cabeza Alembic;
- despliegue manual en 8101;
- pruebas de lectura y escritura relevantes;
- revisión visual del rack 2D/3D y del PDF;
- documentación actualizada;
- confirmación explícita del propietario;
- respaldo separado de producción.
