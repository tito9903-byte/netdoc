import asyncio
from datetime import datetime, timezone
from math import ceil
import secrets
from urllib.parse import quote, urlencode

from fastapi import FastAPI, Form, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import get_settings
from app.core.security import (
    normalize_next_url,
    verify_password,
)
from app.services.netbox_client import (
    NetBoxClient,
    NetBoxError,
)


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="netdoc_session",
    max_age=settings.session_max_age,
    same_site="lax",
    https_only=settings.session_cookie_secure,
)

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)

templates = Jinja2Templates(
    directory="app/templates",
)


DEVICE_STATUSES = [
    ("active", "Activo"),
    ("planned", "Planificado"),
    ("staged", "En preparación"),
    ("failed", "Con falla"),
    ("inventory", "Inventario"),
    ("decommissioning", "En retiro"),
    ("offline", "Fuera de línea"),
]


def is_authenticated(request: Request) -> bool:
    return (
        request.session.get("authenticated") is True
        and bool(request.session.get("username"))
    )


def html_login_redirect(
    request: Request,
) -> RedirectResponse | None:
    if is_authenticated(request):
        return None

    next_url = request.url.path

    if request.url.query:
        next_url = f"{next_url}?{request.url.query}"

    encoded_next = quote(
        next_url,
        safe="",
    )

    return RedirectResponse(
        url=f"/login?next={encoded_next}",
        status_code=303,
    )


def api_unauthorized(
    request: Request,
) -> JSONResponse | None:
    if is_authenticated(request):
        return None

    return JSONResponse(
        status_code=401,
        content={
            "ok": False,
            "error": "Debes iniciar sesión.",
        },
    )


def common_context(
    request: Request,
    current_page: str,
    netbox_connected: bool = True,
) -> dict:
    return {
        "current_page": current_page,
        "current_user": request.session.get(
            "username",
            "",
        ),
        "netbox_connected": netbox_connected,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
    }


def create_page_url(
    page: int,
    query: str,
    site_id: int | None,
    status: str,
    role_id: int | None,
) -> str:
    params: dict[str, str | int] = {
        "page": page,
    }

    if query:
        params["q"] = query

    if site_id:
        params["site_id"] = site_id

    if status:
        params["status"] = status

    if role_id:
        params["role_id"] = role_id

    return f"/devices?{urlencode(params)}"


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.get(
    "/login",
    response_class=HTMLResponse,
)
async def login_page(
    request: Request,
    next: str = "/",
):
    if is_authenticated(request):
        return RedirectResponse(
            url="/",
            status_code=303,
        )

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "page_title": "Iniciar sesión",
            "next_url": normalize_next_url(next),
            "error": None,
        },
    )


@app.post(
    "/login",
    response_class=HTMLResponse,
)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next_url: str = Form("/"),
):
    username_matches = secrets.compare_digest(
        username.strip(),
        settings.admin_username,
    )

    password_matches = False

    if username_matches:
        password_matches = verify_password(
            settings.admin_password_hash,
            password,
        )

    if not username_matches or not password_matches:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            status_code=401,
            context={
                "page_title": "Iniciar sesión",
                "next_url": normalize_next_url(next_url),
                "error": (
                    "El usuario o la contraseña "
                    "no son correctos."
                ),
            },
        )

    request.session.clear()
    request.session["authenticated"] = True
    request.session["username"] = settings.admin_username
    request.session["login_at"] = datetime.now(
        timezone.utc,
    ).isoformat()

    return RedirectResponse(
        url=normalize_next_url(next_url),
        status_code=303,
    )


@app.post("/logout")
async def logout(request: Request):
    request.session.clear()

    return RedirectResponse(
        url="/login",
        status_code=303,
    )


@app.get("/netbox/status")
async def netbox_status(request: Request):
    unauthorized = api_unauthorized(request)

    if unauthorized:
        return unauthorized

    client = NetBoxClient()

    try:
        result = await client.test_connection()

        return {
            "ok": True,
            "netbox": result,
        }

    except NetBoxError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "error": exc.message,
            },
        )


@app.get("/api/dashboard")
async def dashboard_api(request: Request):
    unauthorized = api_unauthorized(request)

    if unauthorized:
        return unauthorized

    client = NetBoxClient()
    summary = await client.dashboard_summary()

    return {
        "ok": True,
        "summary": summary,
    }


@app.get(
    "/",
    response_class=HTMLResponse,
)
async def dashboard(request: Request):
    redirect = html_login_redirect(request)

    if redirect:
        return redirect

    client = NetBoxClient()
    summary = await client.dashboard_summary()

    recent_devices: list[dict] = []
    recent_devices_error: str | None = None

    try:
        recent_devices = await client.recent_devices(
            limit=8,
        )

    except NetBoxError as exc:
        recent_devices_error = exc.message

    netbox_connected = any(
        metric.get("value") is not None
        for metric in summary.values()
    )

    context = {
        **common_context(
            request=request,
            current_page="dashboard",
            netbox_connected=netbox_connected,
        ),
        "page_title": "Dashboard",
        "page_subtitle": (
            "Resumen actualizado de la documentación "
            "en NetBox"
        ),
        "summary": summary,
        "recent_devices": recent_devices,
        "recent_devices_error": recent_devices_error,
    }

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=context,
    )


@app.get(
    "/devices",
    response_class=HTMLResponse,
)
async def devices(
    request: Request,
    q: str = "",
    site_id: int | None = None,
    status: str = "",
    role_id: int | None = None,
    page: int = 1,
):
    redirect = html_login_redirect(request)

    if redirect:
        return redirect

    client = NetBoxClient()

    page = max(page, 1)
    page_size = 25

    try:
        devices_payload, sites, roles = await asyncio.gather(
            client.list_devices(
                page=page,
                page_size=page_size,
                query=q,
                site_id=site_id,
                status=status,
                role_id=role_id,
            ),
            client.list_sites(),
            client.list_device_roles(),
        )

    except NetBoxError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=503,
            context={
                **common_context(
                    request=request,
                    current_page="devices",
                    netbox_connected=False,
                ),
                "page_title": "Error de consulta",
                "page_subtitle": (
                    "No fue posible consultar NetBox"
                ),
                "error_title": (
                    "No se pudieron cargar "
                    "los dispositivos"
                ),
                "error_message": exc.message,
            },
        )

    device_results = devices_payload.get(
        "results",
        [],
    )

    total_count = devices_payload.get(
        "count",
        0,
    )

    if not isinstance(total_count, int):
        total_count = 0

    total_pages = max(
        1,
        ceil(total_count / page_size),
    )

    first_result = (
        ((page - 1) * page_size) + 1
        if total_count
        else 0
    )

    last_result = min(
        page * page_size,
        total_count,
    )

    page_start = max(
        1,
        page - 2,
    )

    page_end = min(
        total_pages,
        page + 2,
    )

    page_links = [
        {
            "number": page_number,
            "active": page_number == page,
            "url": create_page_url(
                page=page_number,
                query=q,
                site_id=site_id,
                status=status,
                role_id=role_id,
            ),
        }
        for page_number in range(
            page_start,
            page_end + 1,
        )
    ]

    previous_url = None

    if page > 1:
        previous_url = create_page_url(
            page=page - 1,
            query=q,
            site_id=site_id,
            status=status,
            role_id=role_id,
        )

    next_url = None

    if page < total_pages:
        next_url = create_page_url(
            page=page + 1,
            query=q,
            site_id=site_id,
            status=status,
            role_id=role_id,
        )

    context = {
        **common_context(
            request=request,
            current_page="devices",
        ),
        "page_title": "Dispositivos",
        "page_subtitle": (
            "Consulta y documentación de equipos "
            "registrados en NetBox"
        ),
        "devices": device_results,
        "sites": sites,
        "roles": roles,
        "statuses": DEVICE_STATUSES,
        "query": q,
        "selected_site_id": site_id,
        "selected_status": status,
        "selected_role_id": role_id,
        "page": page,
        "total_pages": total_pages,
        "total_count": total_count,
        "first_result": first_result,
        "last_result": last_result,
        "page_links": page_links,
        "previous_url": previous_url,
        "next_url": next_url,
    }

    return templates.TemplateResponse(
        request=request,
        name="devices.html",
        context=context,
    )


@app.get(
    "/devices/{device_id}",
    response_class=HTMLResponse,
)
async def device_detail(
    request: Request,
    device_id: int,
):
    redirect = html_login_redirect(request)

    if redirect:
        return redirect

    client = NetBoxClient()

    try:
        device, interfaces = await asyncio.gather(
            client.get_device(device_id),
            client.get_device_interfaces(device_id),
        )

    except NetBoxError as exc:
        status_code = (
            404
            if exc.status_code == 404
            else 503
        )

        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=status_code,
            context={
                **common_context(
                    request=request,
                    current_page="devices",
                    netbox_connected=(
                        exc.status_code != 503
                    ),
                ),
                "page_title": (
                    "Dispositivo no disponible"
                ),
                "page_subtitle": (
                    "No fue posible cargar el equipo"
                ),
                "error_title": (
                    "No se pudo consultar "
                    "el dispositivo"
                ),
                "error_message": exc.message,
            },
        )

    enabled_interfaces = sum(
        1
        for interface in interfaces
        if interface.get("enabled") is True
    )

    connected_interfaces = sum(
        1
        for interface in interfaces
        if interface.get("cable")
        or interface.get("connected_endpoints")
    )

    context = {
        **common_context(
            request=request,
            current_page="devices",
        ),
        "page_title": (
            device.get("name")
            or device.get("display")
            or "Dispositivo"
        ),
        "page_subtitle": (
            "Información general, ubicación "
            "e interfaces"
        ),
        "device": device,
        "interfaces": interfaces,
        "interface_count": len(interfaces),
        "enabled_interfaces": enabled_interfaces,
        "connected_interfaces": connected_interfaces,
    }

    return templates.TemplateResponse(
        request=request,
        name="device_detail.html",
        context=context,
    )

from app.routers.device_create import router as device_create_router
app.include_router(device_create_router)



from app.routers.connections import router as connections_router
app.include_router(connections_router)


from app.routers.racks import router as racks_router
app.include_router(racks_router)
