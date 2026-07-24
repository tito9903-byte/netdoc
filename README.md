# NetDoc

NetDoc es una plataforma independiente que simplifica la consulta y
documentación diaria de infraestructura de red, utilizando NetBox como
fuente oficial de datos.

## Objetivos

- Consultar dispositivos, interfaces, racks y cables.
- Crear equipos mediante formularios guiados.
- Documentar conexiones físicas de manera sencilla.
- Visualizar racks en 2D.
- Incorporar posteriormente topologías y visualización 3D.

## Módulos actuales

- Inicio de sesión administrativo.
- Dashboard.
- Consulta y detalle de dispositivos.
- Creación guiada de equipos.
- Conexiones entre interfaces.
- Visualización de racks en 2D.

## Ramas

- main: producción.
- develop: desarrollo.
- feature/*: cambios individuales.

## Instalación local

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    cp .env.example .env
    .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8100

Nunca se deben subir archivos .env, tokens, contraseñas o claves privadas.
