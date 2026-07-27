from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import access_redirect, common_session_context, request_client_data
from app.core.config import get_settings
from app.core.database import session_scope
from app.routers.device_create import signed_form_token, verify_signed_form_token
from app.services.access_service import record_audit
from app.services.device_type_service import DeviceTypeService, DeviceTypeServiceError


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


@dataclass(frozen=True)
class ComponentField:
    name: str
    label: str
    kind: str = "text"
    required: bool = False
    help_text: str = ""
    default: str = ""
    relation_endpoint: str = ""


@dataclass(frozen=True)
class ComponentKind:
    key: str
    label: str
    plural: str
    endpoint: str
    icon: str
    description: str
    fields: tuple[ComponentField, ...]
    special_create_path: str = ""


COMMON_FIELDS = (
    ComponentField("name", "Nombre", required=True),
    ComponentField("label", "Etiqueta"),
    ComponentField("description", "Descripción", kind="textarea"),
)


COMPONENT_KINDS: dict[str, ComponentKind] = {
    "interface": ComponentKind(
        key="interface",
        label="Interfaz",
        plural="Interfaces",
        endpoint="/api/dcim/interfaces/",
        icon="⇆",
        description="Puerto físico, lógico, virtual o agregado para tráfico de red.",
        fields=(),
        special_create_path="/devices/{device_id}/interfaces/new",
    ),
    "console-port": ComponentKind(
        key="console-port",
        label="Puerto de consola",
        plural="Puertos de consola",
        endpoint="/api/dcim/console-ports/",
        icon=">_",
        description="Puerto local usado para administración por consola.",
        fields=(
            ComponentField("name", "Nombre", required=True),
            ComponentField("type", "Tipo", kind="choice", required=True),
            ComponentField("label", "Etiqueta"),
            ComponentField("mark_connected", "Marcar como conectado", kind="boolean"),
            ComponentField("description", "Descripción", kind="textarea"),
        ),
    ),
    "console-server-port": ComponentKind(
        key="console-server-port",
        label="Puerto de servidor de consola",
        plural="Puertos de servidor de consola",
        endpoint="/api/dcim/console-server-ports/",
        icon="⌘",
        description="Puerto que entrega acceso de consola hacia otro equipo.",
        fields=(
            ComponentField("name", "Nombre", required=True),
            ComponentField("type", "Tipo", kind="choice", required=True),
            ComponentField("label", "Etiqueta"),
            ComponentField("mark_connected", "Marcar como conectado", kind="boolean"),
            ComponentField("description", "Descripción", kind="textarea"),
        ),
    ),
    "power-port": ComponentKind(
        key="power-port",
        label="Entrada de energía",
        plural="Entradas de energía",
        endpoint="/api/dcim/power-ports/",
        icon="⚡",
        description="Conector por el que el dispositivo recibe alimentación.",
        fields=(
            ComponentField("name", "Nombre", required=True),
            ComponentField("type", "Tipo", kind="choice"),
            ComponentField("maximum_draw", "Consumo máximo (W)", kind="integer"),
            ComponentField("allocated_draw", "Consumo asignado (W)", kind="integer"),
            ComponentField("label", "Etiqueta"),
            ComponentField("mark_connected", "Marcar como conectado", kind="boolean"),
            ComponentField("description", "Descripción", kind="textarea"),
        ),
    ),
    "power-outlet": ComponentKind(
        key="power-outlet",
        label="Salida de energía",
        plural="Salidas de energía",
        endpoint="/api/dcim/power-outlets/",
        icon="◉",
        description="Conector que suministra energía desde este dispositivo.",
        fields=(
            ComponentField("name", "Nombre", required=True),
            ComponentField("type", "Tipo", kind="choice"),
            ComponentField(
                "power_port",
                "Entrada de energía asociada",
                kind="relation",
                relation_endpoint="/api/dcim/power-ports/",
            ),
            ComponentField("feed_leg", "Fase", kind="choice"),
            ComponentField("label", "Etiqueta"),
            ComponentField("mark_connected", "Marcar como conectado", kind="boolean"),
            ComponentField("description", "Descripción", kind="textarea"),
        ),
    ),
    "rear-port": ComponentKind(
        key="rear-port",
        label="Puerto trasero",
        plural="Puertos traseros",
        endpoint="/api/dcim/rear-ports/",
        icon="◫",
        description="Terminación posterior de un panel o elemento pasivo.",
        fields=(
            ComponentField("name", "Nombre", required=True),
            ComponentField("type", "Tipo", kind="choice", required=True),
            ComponentField("positions", "Posiciones", kind="integer", required=True, default="1"),
            ComponentField("label", "Etiqueta"),
            ComponentField("mark_connected", "Marcar como conectado", kind="boolean"),
            ComponentField("description", "Descripción", kind="textarea"),
        ),
    ),
    "front-port": ComponentKind(
        key="front-port",
        label="Puerto frontal",
        plural="Puertos frontales",
        endpoint="/api/dcim/front-ports/",
        icon="▣",
        description="Terminación frontal enlazada con un puerto trasero.",
        fields=(
            ComponentField("name", "Nombre", required=True),
            ComponentField("type", "Tipo", kind="choice", required=True),
            ComponentField(
                "rear_port",
                "Puerto trasero",
                kind="relation",
                required=True,
                relation_endpoint="/api/dcim/rear-ports/",
            ),
            ComponentField(
                "rear_port_position",
                "Posición trasera",
                kind="integer",
                required=True,
                default="1",
            ),
            ComponentField("label", "Etiqueta"),
            ComponentField("mark_connected", "Marcar como conectado", kind="boolean"),
            ComponentField("description", "Descripción", kind="textarea"),
        ),
    ),
    "module-bay": ComponentKind(
        key="module-bay",
        label="Bahía de módulo",
        plural="Bahías de módulo",
        endpoint="/api/dcim/module-bays/",
        icon="▤",
        description="Espacio para insertar una tarjeta o módulo reemplazable.",
        fields=(
            ComponentField("name", "Nombre", required=True),
            ComponentField("label", "Etiqueta"),
            ComponentField("position", "Posición"),
            ComponentField("description", "Descripción", kind="textarea"),
        ),
    ),
    "device-bay": ComponentKind(
        key="device-bay",
        label="Bahía de dispositivo",
        plural="Bahías de dispositivo",
        endpoint="/api/dcim/device-bays/",
        icon="▥",
        description="Espacio físico para instalar otro dispositivo hijo.",
        fields=(
            ComponentField("name", "Nombre", required=True),
            ComponentField("label", "Etiqueta"),
            ComponentField("description", "Descripción", kind="textarea"),
        ),
    ),
    "inventory-item": ComponentKind(
        key="inventory-item",
        label="Elemento de inventario",
        plural="Elementos de inventario",
        endpoint="/api/dcim/inventory-items/",
        icon="◇",
        description="Pieza interna, transceptor, fuente, ventilador u otro repuesto.",
        fields=(
            ComponentField("name", "Nombre", required=True),
            ComponentField(
                "manufacturer",
                "Fabricante",
                kind="relation-global",
                relation_endpoint="/api/dcim/manufacturers/",
            ),
            ComponentField(
                "parent",
                "Elemento padre",
                kind="relation",
                relation_endpoint="/api/dcim/inventory-items/",
            ),
            ComponentField("part_id", "Número de parte"),
            ComponentField("serial", "Número de serie"),
            ComponentField("asset_tag", "Etiqueta de activo"),
            ComponentField("discovered", "Descubierto automáticamente", kind="boolean"),
            ComponentField("description", "Descripción", kind="textarea"),
        ),
    ),
}


def context(request: Request, **extra: object) -> dict[str, object]:
    return {
        **common_session_context(request),
        "current_page": "devices",
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        **extra,
    }


def audit_component(
    request: Request,
    *,
    action: str,
    resource_id: int,
    detail: str,
    success: bool,
) -> None:
    ip_address, user_agent = request_client_data(request)
    user_id = request.session.get("user_id")
    with session_scope() as session:
        record_audit(
            session,
            action=action,
            resource="device_component",
            resource_id=str(resource_id),
            user_id=user_id if isinstance(user_id, int) else None,
            username=str(request.session.get("username") or "desconocido"),
            detail=detail,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )


def component_kind(kind: str) -> ComponentKind:
    specification = COMPONENT_KINDS.get(str(kind or "").strip().casefold())
    if specification is None:
        raise DeviceTypeServiceError("Selecciona un tipo de componente válido.", 404)
    return specification


def nested_label(value: Any) -> str:
    if isinstance(value, dict):
        return str(
            value.get("display")
            or value.get("name")
            or value.get("label")
            or value.get("value")
            or ""
        )
    return str(value or "")


def nested_id(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, dict) and isinstance(value.get("id"), int):
        return int(value["id"])
    return None


def parse_integer(value: Any, label: str, *, required: bool = False) -> int | None:
    clean = str(value or "").strip()
    if not clean:
        if required:
            raise DeviceTypeServiceError(f"Completa {label.lower()}.", 400)
        return None
    try:
        parsed = int(clean)
    except ValueError as exc:
        raise DeviceTypeServiceError(f"{label} debe ser un número entero.", 400) from exc
    if parsed < 0:
        raise DeviceTypeServiceError(f"{label} no puede ser negativo.", 400)
    return parsed


def parse_relation(value: Any, label: str, *, required: bool = False) -> int | None:
    clean = str(value or "").strip()
    if not clean:
        if required:
            raise DeviceTypeServiceError(f"Selecciona {label.lower()}.", 400)
        return None
    if not clean.isdigit() or int(clean) < 1:
        raise DeviceTypeServiceError(f"Selecciona {label.lower()} válido.", 400)
    return int(clean)


def redirect_with_message(device_id: int, *, notice: str = "", error: str = ""):
    params = {
        key: value
        for key, value in {"notice": notice, "error": error}.items()
        if value
    }
    query = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(
        f"/devices/{device_id}/components{query}",
        status_code=303,
    )


async def load_device(service: DeviceTypeService, device_id: int) -> dict[str, Any]:
    device = await service.request("GET", f"/api/dcim/devices/{device_id}/")
    if not isinstance(device, dict):
        raise DeviceTypeServiceError("NetBox devolvió un dispositivo inesperado.", 502)
    return device


async def load_group(
    service: DeviceTypeService,
    device_id: int,
    specification: ComponentKind,
) -> dict[str, Any]:
    try:
        rows = await service.get_all(
            specification.endpoint,
            params={"device_id": device_id, "ordering": "name"},
        )
        error = ""
    except DeviceTypeServiceError as exc:
        rows = []
        error = exc.message

    prepared = []
    for row in rows:
        prepared.append({
            **row,
            "_name": str(row.get("name") or row.get("display") or "Sin nombre"),
            "_type": nested_label(row.get("type")),
            "_detail": str(
                row.get("description")
                or row.get("label")
                or row.get("part_id")
                or ""
            ),
        })
    return {
        "kind": specification,
        "rows": prepared,
        "count": len(prepared),
        "error": error,
    }


@router.get("/devices/{device_id}/components", response_class=HTMLResponse)
async def device_components_page(request: Request, device_id: int):
    redirect = access_redirect(request, "devices.view")
    if redirect:
        return redirect

    service = DeviceTypeService()
    try:
        device = await load_device(service, device_id)
        groups = await asyncio.gather(*(
            load_group(service, device_id, specification)
            for specification in COMPONENT_KINDS.values()
        ))
    except DeviceTypeServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=404 if exc.status_code == 404 else 503,
            context=context(
                request,
                page_title="Componentes no disponibles",
                page_subtitle="No fue posible consultar el dispositivo",
                error_title="No se pudieron cargar los componentes",
                error_message=exc.message,
                netbox_connected=exc.status_code != 503,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="device_components.html",
        context=context(
            request,
            page_title="Componentes del dispositivo",
            page_subtitle="Inventario físico y lógico registrado directamente en NetBox",
            device=device,
            device_id=device_id,
            groups=groups,
            component_count=sum(int(group["count"]) for group in groups),
        ),
    )


@router.get("/devices/{device_id}/components/new", response_class=HTMLResponse)
async def device_component_picker(request: Request, device_id: int):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    try:
        device = await load_device(DeviceTypeService(), device_id)
    except DeviceTypeServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=404 if exc.status_code == 404 else 503,
            context=context(
                request,
                page_title="Dispositivo no disponible",
                page_subtitle="No fue posible preparar el componente",
                error_title="No se pudo cargar el dispositivo",
                error_message=exc.message,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="device_component_picker.html",
        context=context(
            request,
            page_title="Crear componente",
            page_subtitle="Selecciona qué elemento deseas agregar al dispositivo",
            device=device,
            device_id=device_id,
            component_kinds=list(COMPONENT_KINDS.values()),
        ),
    )


async def choices_for_field(
    service: DeviceTypeService,
    device_id: int,
    specification: ComponentKind,
    field: ComponentField,
    post_fields: dict[str, Any],
) -> list[dict[str, str]]:
    if field.kind == "choice":
        raw_choices = (post_fields.get(field.name) or {}).get("choices", [])
        choices = []
        for item in raw_choices if isinstance(raw_choices, list) else []:
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            label = item.get("display_name") or item.get("label") or value
            if value not in (None, ""):
                choices.append({"value": str(value), "label": str(label)})
        return choices

    if field.kind not in {"relation", "relation-global"} or not field.relation_endpoint:
        return []

    params: dict[str, Any] = {"ordering": "name"}
    if field.kind == "relation":
        params["device_id"] = device_id
    rows = await service.get_all(field.relation_endpoint, params=params)
    return [
        {
            "value": str(row["id"]),
            "label": str(row.get("display") or row.get("name") or row["id"]),
        }
        for row in rows
        if isinstance(row.get("id"), int)
    ]


async def load_component_form(
    request: Request,
    device_id: int,
    kind: str,
    *,
    error: str = "",
    status_code: int = 200,
):
    try:
        specification = component_kind(kind)
    except DeviceTypeServiceError as exc:
        return redirect_with_message(device_id, error=exc.message)

    if specification.special_create_path:
        return RedirectResponse(
            specification.special_create_path.format(device_id=device_id),
            status_code=303,
        )

    service = DeviceTypeService()
    try:
        device, options = await asyncio.gather(
            load_device(service, device_id),
            service.request("OPTIONS", specification.endpoint),
        )
        post_fields = (
            (options.get("actions") or {}).get("POST", {})
            if isinstance(options, dict)
            else {}
        )
        fields = []
        for field in specification.fields:
            choices = await choices_for_field(
                service,
                device_id,
                specification,
                field,
                post_fields if isinstance(post_fields, dict) else {},
            )
            fields.append({
                "name": field.name,
                "label": field.label,
                "kind": field.kind,
                "required": field.required,
                "help_text": field.help_text,
                "default": field.default,
                "choices": choices,
                "supported": not post_fields or field.name in post_fields,
            })
    except DeviceTypeServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=404 if exc.status_code == 404 else 503,
            context=context(
                request,
                page_title="Componente no disponible",
                page_subtitle="No fue posible preparar el formulario",
                error_title="No se pudo cargar el componente",
                error_message=exc.message,
                netbox_connected=exc.status_code != 503,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="device_component_form.html",
        status_code=status_code,
        context=context(
            request,
            page_title=f"Crear {specification.label.lower()}",
            page_subtitle="Agregar el componente directamente al dispositivo en NetBox",
            device=device,
            device_id=device_id,
            component_kind=specification,
            fields=fields,
            csrf_token=signed_form_token(
                request,
                f"device-component-create:{device_id}:{specification.key}",
            ),
            error=error,
        ),
    )


@router.get(
    "/devices/{device_id}/components/{kind}/new",
    response_class=HTMLResponse,
)
async def device_component_form(
    request: Request,
    device_id: int,
    kind: str,
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await load_component_form(request, device_id, kind)


@router.post("/devices/{device_id}/components/{kind}/actions/create")
async def device_component_create(
    request: Request,
    device_id: int,
    kind: str,
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    try:
        specification = component_kind(kind)
    except DeviceTypeServiceError as exc:
        return redirect_with_message(device_id, error=exc.message)

    if specification.special_create_path:
        return RedirectResponse(
            specification.special_create_path.format(device_id=device_id),
            status_code=303,
        )

    form = await request.form()
    csrf_token = str(form.get("csrf_token") or "")
    namespace = f"device-component-create:{device_id}:{specification.key}"
    if not verify_signed_form_token(request, csrf_token, namespace):
        return await load_component_form(
            request,
            device_id,
            kind,
            error="La sesión de seguridad venció. Abre nuevamente el formulario.",
            status_code=403,
        )
    if not settings.netbox_write_enabled:
        return await load_component_form(
            request,
            device_id,
            kind,
            error="La escritura en NetBox está deshabilitada.",
            status_code=403,
        )

    try:
        service = DeviceTypeService()
        options = await service.request("OPTIONS", specification.endpoint)
        post_fields = (
            (options.get("actions") or {}).get("POST", {})
            if isinstance(options, dict)
            else {}
        )
        allowed = set(post_fields.keys()) if isinstance(post_fields, dict) else set()

        payload: dict[str, Any] = {"device": device_id}
        for field in specification.fields:
            if allowed and field.name not in allowed:
                continue
            raw = form.get(field.name)
            if field.kind == "boolean":
                value: Any = str(raw or "").casefold() in {"1", "true", "on", "yes"}
            elif field.kind == "integer":
                value = parse_integer(raw, field.label, required=field.required)
            elif field.kind in {"relation", "relation-global"}:
                value = parse_relation(raw, field.label, required=field.required)
            else:
                value = str(raw or "").strip()
                if field.required and not value:
                    raise DeviceTypeServiceError(
                        f"Completa {field.label.lower()}.",
                        400,
                    )
                if field.name == "asset_tag" and not value:
                    value = None
            payload[field.name] = value

        name = str(payload.get("name") or "").strip()
        if not name:
            raise DeviceTypeServiceError("Escribe el nombre del componente.", 400)

        result = await service.request(
            "POST",
            specification.endpoint,
            json_body=payload,
        )
        if not isinstance(result, dict):
            raise DeviceTypeServiceError(
                "NetBox creó el componente, pero devolvió un formato inesperado.",
                502,
            )
    except DeviceTypeServiceError as exc:
        audit_component(
            request,
            action="DEVICE_COMPONENT_CREATE",
            resource_id=device_id,
            detail=f"{specification.label}: {exc.message}",
            success=False,
        )
        return await load_component_form(
            request,
            device_id,
            kind,
            error=exc.message,
            status_code=exc.status_code or 400,
        )

    created_id = int(result.get("id") or device_id)
    audit_component(
        request,
        action="DEVICE_COMPONENT_CREATE",
        resource_id=created_id,
        detail=(
            f"{specification.label} {name} creado en el dispositivo #{device_id}."
        ),
        success=True,
    )
    return redirect_with_message(
        device_id,
        notice=f"{specification.label} {name} creado correctamente.",
    )
