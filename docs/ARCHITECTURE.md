# Arquitectura

NetDoc es una aplicación FastAPI que consume la API REST de NetBox.

## Componentes

- FastAPI: aplicación web y rutas.
- Jinja2: plantillas HTML.
- HTTPX: comunicación con NetBox.
- SessionMiddleware: sesiones de usuario.
- Argon2: validación de contraseñas.
- NetBox: inventario oficial y protección técnica final.

## Responsabilidades

NetDoc controla la experiencia de usuario, formularios guiados,
validaciones adicionales, auditoría funcional y permisos internos.

NetBox controla dispositivos, interfaces, racks, cables, direcciones,
permisos de objetos y el historial técnico de cambios.
