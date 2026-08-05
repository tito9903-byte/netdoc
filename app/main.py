import asyncio
from contextlib import asynccontextmanager
from math import ceil
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.core.auth import (
    access_redirect,
    api_access_response,
    apply_identity_to_session,
    common_session_context,
    is_authenticated,
    PermissionMiddleware,
    request_client_data,
)
from app.core.config import get_settings
from app.core.database import initialize_database, session_scope
from app.core.security import normalize_next_url
from app.services.access_service import (
    authenticate_user,
    login_throttle_status,
    record_audit,
)
from app.services.netbox_client import (
    NetBoxClient,
    NetBoxError,
)


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

app.add_middleware(PermissionMiddleware)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie=settings.session_cookie_name,
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


def parse_optional_positive_int(
    value: str | int | None,
) -> int | None:
    if isinstance(value, int):
        return value if value > 0 else None

    if not isinstance(value, str):
        return None

    try:
        parsed = int(value.strip())
    except ValueError:
        return None

    return parsed if parsed > 0 else None


def common_context(
    request: Request,
    current_page: str,
    netbox_connected: bool = True,
) -> dict:
    return {
        **common_session_context(request),
        "current_page": current_page,
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
    ip_address, user_agent = request_client_data(request)

    with session_scope() as session:
        throttle = login_throttle_status(
            session,
            username=username,
            ip_address=ip_address,
            max_attempts=settings.login_max_attempts,
            window_seconds=settings.login_window_seconds,
        )

        if throttle.blocked:
            record_audit(
                session,
                action="LOGIN_BLOCKED",
                resource="session",
                username=username.strip().lower() or "desconocido",
                detail=(
                    "Intento temporalmente bloqueado por exceso "
                    "de fallos recientes."
                ),
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                status_code=429,
                headers={
                    "Retry-After": str(throttle.retry_after_seconds),
                },
                context={
                    "page_title": "Iniciar sesión",
                    "next_url": normalize_next_url(next_url),
                    "error": (
                        "Demasiados intentos fallidos. "
                        "Espera unos minutos e inténtalo nuevamente."
                    ),
                },
            )

        identity = authenticate_user(
            session,
            username=username,
            password=password,
        )

        if identity is None:
            record_audit(
                session,
                action="LOGIN_FAILED",
                resource="session",
                username=username.strip().lower() or "desconocido",
                detail="Credenciales inválidas o cuenta inactiva.",
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
            )

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

        record_audit(
            session,
            action="LOGIN_SUCCESS",
            resource="session",
            user_id=identity.id,
            username=identity.username,
            detail=f"Inicio de sesión con rol {identity.role_name}.",
            ip_address=ip_address,
            user_agent=user_agent,
        )

    apply_identity_to_session(request, identity)

    return RedirectResponse(
        url=normalize_next_url(next_url),
        status_code=303,
    )


@app.post("/logout")
async def logout(request: Request):
    if is_authenticated(request):
        ip_address, user_agent = request_client_data(request)

        with session_scope() as session:
            user_id = request.session.get("user_id")
            record_audit(
                session,
                action="LOGOUT",
                resource="session",
                user_id=(
                    user_id
                    if isinstance(user_id, int)
                    else None
                ),
                username=str(
                    request.session.get("username") or "desconocido"
                ),
                detail="Cierre de sesión.",
                ip_address=ip_address,
                user_agent=user_agent,
            )

    request.session.clear()

    return RedirectResponse(
        url="/login",
        status_code=303,
    )


@app.get(
    "/forbidden",
    response_class=HTMLResponse,
)
async def forbidden_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="forbidden.html",
        status_code=403,
        context={
            **common_context(
                request=request,
                current_page="forbidden",
            ),
            "page_title": "Acceso restringido",
            "page_subtitle": "El rol asignado no incluye este permiso",
        },
    )


@app.get("/netbox/status")
async def netbox_status(request: Request):
    unauthorized = api_access_response(
        request,
        "dashboard.view",
    )

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
    unauthorized = api_access_response(
        request,
        "dashboard.view",
    )

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
    redirect = access_redirect(
        request,
        "dashboard.view",
    )

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
    site_id: str = "",
    status: str = "",
    role_id: str = "",
    page: str = "1",
):
    redirect = access_redirect(
        request,
        "devices.view",
    )

    if redirect:
        return redirect

    client = NetBoxClient()

    query = q.strip()
    selected_site_id = parse_optional_positive_int(site_id)
    selected_status = status.strip()
    selected_role_id = parse_optional_positive_int(role_id)
    selected_page = parse_optional_positive_int(page) or 1
    page_size = 25

    try:
        devices_payload, sites, roles = await asyncio.gather(
            client.list_devices(
                page=selected_page,
                page_size=page_size,
                query=query,
                site_id=selected_site_id,
                status=selected_status,
                role_id=selected_role_id,
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
        ((selected_page - 1) * page_size) + 1
        if total_count
        else 0
    )

    last_result = min(
        selected_page * page_size,
        total_count,
    )

    page_start = max(
        1,
        selected_page - 2,
    )

    page_end = min(
        total_pages,
        selected_page + 2,
    )

    page_links = [
        {
            "number": page_number,
            "active": page_number == selected_page,
            "url": create_page_url(
                page=page_number,
                query=query,
                site_id=selected_site_id,
                status=selected_status,
                role_id=selected_role_id,
            ),
        }
        for page_number in range(
            page_start,
            page_end + 1,
        )
    ]

    previous_url = None

    if selected_page > 1:
        previous_url = create_page_url(
            page=selected_page - 1,
            query=query,
            site_id=selected_site_id,
            status=selected_status,
            role_id=selected_role_id,
        )

    next_url = None

    if selected_page < total_pages:
        next_url = create_page_url(
            page=selected_page + 1,
            query=query,
            site_id=selected_site_id,
            status=selected_status,
            role_id=selected_role_id,
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
        "query": query,
        "selected_site_id": selected_site_id,
        "selected_status": selected_status,
        "selected_role_id": selected_role_id,
        "page": selected_page,
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
    redirect = access_redirect(
        request,
        "devices.view",
    )

    if redirect:
        return redirect

    client = NetBoxClient()

    try:
        device, interfaces, interface_ip_addresses = await asyncio.gather(
            client.get_device(device_id),
            client.get_device_interfaces(device_id),
            client.get_device_interface_ip_addresses(device_id),
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

    ip_addresses_by_interface: dict[int, list[dict[str, Any]]] = {}

    for ip_address in interface_ip_addresses:
        assigned_object_type = ip_address.get("assigned_object_type")

        if assigned_object_type not in (None, "dcim.interface"):
            continue

        assigned_object = ip_address.get("assigned_object") or {}
        interface_id = (
            ip_address.get("assigned_object_id")
            or assigned_object.get("id")
        )

        if not isinstance(interface_id, int):
            continue

        ip_addresses_by_interface.setdefault(interface_id, []).append(
            ip_address
        )

    interfaces = [
        {
            **interface,
            "_ip_addresses": ip_addresses_by_interface.get(
                interface.get("id"),
                [],
            ),
        }
        for interface in interfaces
    ]

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


from app.routers.admin import router as admin_router
from app.routers.connections import router as connections_router
from app.routers.device_create import router as device_create_router
from app.routers.racks import router as racks_router
from app.routers.profile import router as profile_router
from app.routers.search import router as search_router
from app.routers.sites import router as sites_router
from app.routers.system import router as system_router

app.include_router(device_create_router)
app.include_router(connections_router)
app.include_router(racks_router)
app.include_router(profile_router)
app.include_router(search_router)
app.include_router(sites_router)
app.include_router(system_router)
app.include_router(admin_router)
