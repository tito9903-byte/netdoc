from __future__ import annotations

from collections import defaultdict
import csv
from datetime import datetime, timezone
import io
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.core.auth import (
    access_redirect,
    apply_identity_to_session,
    common_session_context,
    csrf_token,
    request_client_data,
    verify_csrf,
)
from app.core.config import get_settings
from app.core.database import session_scope
from app.services.access_service import (
    AccessServiceError,
    count_active_admins,
    create_role,
    create_user,
    delete_role,
    delete_user,
    export_audit_events,
    get_identity,
    get_role,
    get_user,
    list_audit_events,
    list_permissions,
    list_roles,
    list_users,
    record_audit,
    set_user_password,
    update_role,
    update_user,
)


router = APIRouter(prefix="/admin")
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


def context(
    request: Request,
    *,
    current_page: str,
    **extra: object,
) -> dict[str, object]:
    return {
        **common_session_context(request),
        "current_page": current_page,
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        **extra,
    }


def actor(request: Request) -> tuple[int | None, str]:
    user_id = request.session.get("user_id")
    username = str(request.session.get("username") or "sistema")

    return (
        user_id if isinstance(user_id, int) else None,
        username,
    )


def audit_request(
    request: Request,
    session,
    *,
    action: str,
    resource: str,
    resource_id: str | int | None = None,
    detail: str = "",
    success: bool = True,
) -> None:
    user_id, username = actor(request)
    ip_address, user_agent = request_client_data(request)

    record_audit(
        session,
        action=action,
        resource=resource,
        resource_id=resource_id,
        detail=detail,
        success=success,
        user_id=user_id,
        username=username,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def redirect_with_message(
    path: str,
    message: str,
) -> RedirectResponse:
    return RedirectResponse(
        url=f"{path}?{urlencode({'message': message})}",
        status_code=303,
    )


def permission_groups(permissions) -> dict[str, list]:
    groups: dict[str, list] = defaultdict(list)

    for permission in permissions:
        groups[permission.category].append(permission)

    return dict(groups)


@router.get(
    "/users",
    response_class=HTMLResponse,
)
async def users_page(
    request: Request,
    message: str = "",
    q: str = "",
    role_id: int | None = None,
    status: str = "",
):
    redirect = access_redirect(request, "users.manage")
    if redirect:
        return redirect

    with session_scope() as session:
        all_users = list_users(session)
        users = list_users(
            session,
            query=q,
            role_id=role_id,
            status=status,
        )
        roles = list_roles(session)

        return templates.TemplateResponse(
            request=request,
            name="admin_users.html",
            context=context(
                request,
                current_page="users",
                page_title="Usuarios",
                page_subtitle=(
                    "Cuentas, estado de acceso y roles asignados"
                ),
                users=users,
                roles=roles,
                total_users=len(all_users),
                active_users=sum(1 for user in all_users if user.is_active),
                query=q,
                selected_role_id=role_id,
                selected_status=status,
                current_user_id=request.session.get("user_id"),
                message=message,
                csrf_token=csrf_token(request, "users"),
            ),
        )


@router.get(
    "/users/new",
    response_class=HTMLResponse,
)
async def user_create_page(request: Request):
    redirect = access_redirect(request, "users.manage")
    if redirect:
        return redirect

    with session_scope() as session:
        roles = list_roles(session)

        return templates.TemplateResponse(
            request=request,
            name="admin_user_form.html",
            context=context(
                request,
                current_page="users",
                page_title="Crear usuario",
                page_subtitle="Nueva cuenta de acceso a NetDoc",
                mode="create",
                user=None,
                roles=roles,
                form_data={},
                errors=[],
                csrf_token=csrf_token(request, "users"),
            ),
        )


@router.post(
    "/users/new",
    response_class=HTMLResponse,
)
async def user_create_submit(
    request: Request,
    csrf: str = Form(...),
    username: str = Form(""),
    full_name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    role_id: int = Form(...),
    is_active: str | None = Form(None),
):
    redirect = access_redirect(request, "users.manage")
    if redirect:
        return redirect

    form_data = {
        "username": username,
        "full_name": full_name,
        "email": email,
        "role_id": role_id,
        "is_active": is_active is not None,
    }

    with session_scope() as session:
        roles = list_roles(session)

        if not verify_csrf(request, csrf, "users"):
            errors = ["La sesión del formulario expiró."]
        else:
            errors = []

            try:
                user = create_user(
                    session,
                    username=username,
                    full_name=full_name,
                    email=email,
                    password=password,
                    role_id=role_id,
                    is_active=is_active is not None,
                )
                audit_request(
                    request,
                    session,
                    action="USER_CREATE",
                    resource="user",
                    resource_id=user.id,
                    detail=(
                        f"Usuario {user.username} creado "
                        f"con rol {user.role.name}."
                    ),
                )

                return redirect_with_message(
                    "/admin/users",
                    f"Usuario {user.username} creado.",
                )

            except AccessServiceError as exc:
                errors.append(str(exc))
                audit_request(
                    request,
                    session,
                    action="USER_CREATE",
                    resource="user",
                    detail=f"Creación rechazada: {exc}",
                    success=False,
                )

        return templates.TemplateResponse(
            request=request,
            name="admin_user_form.html",
            status_code=400,
            context=context(
                request,
                current_page="users",
                page_title="Crear usuario",
                page_subtitle="Nueva cuenta de acceso a NetDoc",
                mode="create",
                user=None,
                roles=roles,
                form_data=form_data,
                errors=errors,
                csrf_token=csrf_token(request, "users"),
            ),
        )


@router.get(
    "/users/{user_id}/edit",
    response_class=HTMLResponse,
)
async def user_edit_page(
    request: Request,
    user_id: int,
):
    redirect = access_redirect(request, "users.manage")
    if redirect:
        return redirect

    with session_scope() as session:
        user = get_user(session, user_id)
        roles = list_roles(session)

        if user is None:
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                status_code=404,
                context=context(
                    request,
                    current_page="users",
                    page_title="Usuario no encontrado",
                    page_subtitle="La cuenta solicitada no existe",
                    error_title="No se encontró el usuario",
                    error_message=(
                        "El identificador indicado no pertenece "
                        "a una cuenta de NetDoc."
                    ),
                ),
            )

        return templates.TemplateResponse(
            request=request,
            name="admin_user_form.html",
            context=context(
                request,
                current_page="users",
                page_title=f"Editar {user.username}",
                page_subtitle="Datos, rol y estado de la cuenta",
                mode="edit",
                user=user,
                roles=roles,
                form_data={},
                errors=[],
                csrf_token=csrf_token(request, "users"),
            ),
        )


@router.post(
    "/users/{user_id}/edit",
    response_class=HTMLResponse,
)
async def user_edit_submit(
    request: Request,
    user_id: int,
    csrf: str = Form(...),
    username: str = Form(""),
    full_name: str = Form(""),
    email: str = Form(""),
    role_id: int = Form(...),
    is_active: str | None = Form(None),
):
    redirect = access_redirect(request, "users.manage")
    if redirect:
        return redirect

    form_data = {
        "username": username,
        "full_name": full_name,
        "email": email,
        "role_id": role_id,
        "is_active": is_active is not None,
    }

    with session_scope() as session:
        user = get_user(session, user_id)
        roles = list_roles(session)

        if user is None:
            return RedirectResponse("/admin/users", status_code=303)

        errors: list[str] = []

        if not verify_csrf(request, csrf, "users"):
            errors.append("La sesión del formulario expiró.")

        current_user_id = request.session.get("user_id")
        requested_active = is_active is not None

        if user.id == current_user_id and not requested_active:
            errors.append("No puedes desactivar tu propia cuenta.")

        if (
            user.is_active
            and user.role.code == "administrador"
            and (
                not requested_active
                or role_id != user.role_id
            )
            and count_active_admins(session) <= 1
        ):
            errors.append(
                "Debe permanecer al menos un administrador activo."
            )

        if not errors:
            try:
                user = update_user(
                    session,
                    user,
                    username=username,
                    full_name=full_name,
                    email=email,
                    role_id=role_id,
                    is_active=requested_active,
                )
                audit_request(
                    request,
                    session,
                    action="USER_UPDATE",
                    resource="user",
                    resource_id=user.id,
                    detail=(
                        f"Usuario {user.username} actualizado; "
                        f"rol {user.role.name}; "
                        f"activo={user.is_active}."
                    ),
                )

                if user.id == current_user_id:
                    identity = get_identity(session, user.id)
                    if identity:
                        apply_identity_to_session(request, identity)

                return redirect_with_message(
                    "/admin/users",
                    f"Usuario {user.username} actualizado.",
                )

            except AccessServiceError as exc:
                errors.append(str(exc))
                audit_request(
                    request,
                    session,
                    action="USER_UPDATE",
                    resource="user",
                    resource_id=user.id,
                    detail=f"Actualización rechazada: {exc}",
                    success=False,
                )

        return templates.TemplateResponse(
            request=request,
            name="admin_user_form.html",
            status_code=400,
            context=context(
                request,
                current_page="users",
                page_title=f"Editar {user.username}",
                page_subtitle="Datos, rol y estado de la cuenta",
                mode="edit",
                user=user,
                roles=roles,
                form_data=form_data,
                errors=errors,
                csrf_token=csrf_token(request, "users"),
            ),
        )


@router.post("/users/{user_id}/password")
async def user_password_submit(
    request: Request,
    user_id: int,
    csrf: str = Form(...),
    password: str = Form(...),
):
    redirect = access_redirect(request, "users.manage")
    if redirect:
        return redirect

    with session_scope() as session:
        user = get_user(session, user_id)

        if user is None:
            return RedirectResponse("/admin/users", status_code=303)

        if not verify_csrf(request, csrf, "users"):
            return redirect_with_message(
                f"/admin/users/{user_id}/edit",
                "La sesión del formulario expiró.",
            )

        try:
            set_user_password(session, user, password)
            audit_request(
                request,
                session,
                action="USER_PASSWORD_RESET",
                resource="user",
                resource_id=user.id,
                detail=f"Contraseña restablecida para {user.username}.",
            )

            return redirect_with_message(
                "/admin/users",
                f"Contraseña actualizada para {user.username}.",
            )

        except AccessServiceError as exc:
            audit_request(
                request,
                session,
                action="USER_PASSWORD_RESET",
                resource="user",
                resource_id=user.id,
                detail=f"Cambio rechazado: {exc}",
                success=False,
            )

            return redirect_with_message(
                f"/admin/users/{user_id}/edit",
                str(exc),
            )


@router.post("/users/{user_id}/delete")
async def user_delete_submit(
    request: Request,
    user_id: int,
    csrf: str = Form(...),
):
    redirect = access_redirect(request, "users.manage")
    if redirect:
        return redirect

    with session_scope() as session:
        user = get_user(session, user_id)

        if user is None:
            return RedirectResponse("/admin/users", status_code=303)

        if not verify_csrf(request, csrf, "users"):
            return redirect_with_message(
                "/admin/users",
                "La sesión del formulario expiró.",
            )

        current_user_id = request.session.get("user_id")

        if user.id == current_user_id:
            return redirect_with_message(
                "/admin/users",
                "No puedes eliminar tu propia cuenta.",
            )

        if (
            user.is_active
            and user.role.code == "administrador"
            and count_active_admins(session) <= 1
        ):
            return redirect_with_message(
                "/admin/users",
                "Debe permanecer al menos un administrador activo.",
            )

        username = user.username
        role_name = user.role.name
        delete_user(session, user)
        audit_request(
            request,
            session,
            action="USER_DELETE",
            resource="user",
            resource_id=user_id,
            detail=(
                f"Usuario {username} eliminado; "
                f"rol anterior {role_name}."
            ),
        )

        return redirect_with_message(
            "/admin/users",
            f"Usuario {username} eliminado.",
        )


@router.get(
    "/roles",
    response_class=HTMLResponse,
)
async def roles_page(
    request: Request,
    message: str = "",
):
    redirect = access_redirect(request, "roles.manage")
    if redirect:
        return redirect

    with session_scope() as session:
        roles = list_roles(session)

        return templates.TemplateResponse(
            request=request,
            name="admin_roles.html",
            context=context(
                request,
                current_page="roles",
                page_title="Roles y permisos",
                page_subtitle=(
                    "Perfiles de acceso y privilegios de NetDoc"
                ),
                roles=roles,
                message=message,
                csrf_token=csrf_token(request, "roles"),
            ),
        )


@router.get(
    "/roles/new",
    response_class=HTMLResponse,
)
async def role_create_page(request: Request):
    redirect = access_redirect(request, "roles.manage")
    if redirect:
        return redirect

    with session_scope() as session:
        permissions = list_permissions(session)

        return templates.TemplateResponse(
            request=request,
            name="admin_role_form.html",
            context=context(
                request,
                current_page="roles",
                page_title="Crear rol",
                page_subtitle="Nuevo perfil de permisos",
                mode="create",
                role=None,
                permission_groups=permission_groups(permissions),
                selected_permissions=set(),
                form_data={},
                errors=[],
                csrf_token=csrf_token(request, "roles"),
            ),
        )


@router.post(
    "/roles/new",
    response_class=HTMLResponse,
)
async def role_create_submit(
    request: Request,
    csrf: str = Form(...),
    name: str = Form(""),
    code: str = Form(""),
    description: str = Form(""),
    permissions: list[str] = Form(default=[]),
):
    redirect = access_redirect(request, "roles.manage")
    if redirect:
        return redirect

    form_data = {
        "name": name,
        "code": code,
        "description": description,
    }

    with session_scope() as session:
        available_permissions = list_permissions(session)
        errors: list[str] = []

        if not verify_csrf(request, csrf, "roles"):
            errors.append("La sesión del formulario expiró.")

        if not errors:
            try:
                role = create_role(
                    session,
                    name=name,
                    code=code,
                    description=description,
                    permission_codes_value=permissions,
                )
                audit_request(
                    request,
                    session,
                    action="ROLE_CREATE",
                    resource="role",
                    resource_id=role.id,
                    detail=f"Rol {role.name} creado.",
                )

                return redirect_with_message(
                    "/admin/roles",
                    f"Rol {role.name} creado.",
                )

            except AccessServiceError as exc:
                errors.append(str(exc))
                audit_request(
                    request,
                    session,
                    action="ROLE_CREATE",
                    resource="role",
                    detail=f"Creación rechazada: {exc}",
                    success=False,
                )

        return templates.TemplateResponse(
            request=request,
            name="admin_role_form.html",
            status_code=400,
            context=context(
                request,
                current_page="roles",
                page_title="Crear rol",
                page_subtitle="Nuevo perfil de permisos",
                mode="create",
                role=None,
                permission_groups=permission_groups(
                    available_permissions
                ),
                selected_permissions=set(permissions),
                form_data=form_data,
                errors=errors,
                csrf_token=csrf_token(request, "roles"),
            ),
        )


@router.get(
    "/roles/{role_id}/edit",
    response_class=HTMLResponse,
)
async def role_edit_page(
    request: Request,
    role_id: int,
    message: str = "",
):
    redirect = access_redirect(request, "roles.manage")
    if redirect:
        return redirect

    with session_scope() as session:
        role = get_role(session, role_id)
        permissions = list_permissions(session)

        if role is None:
            return RedirectResponse("/admin/roles", status_code=303)

        return templates.TemplateResponse(
            request=request,
            name="admin_role_form.html",
            context=context(
                request,
                current_page="roles",
                page_title=f"Editar {role.name}",
                page_subtitle="Nombre, descripción y permisos",
                mode="edit",
                role=role,
                permission_groups=permission_groups(permissions),
                selected_permissions={
                    permission.code
                    for permission in role.permissions
                },
                form_data={},
                errors=([message] if message else []),
                csrf_token=csrf_token(request, "roles"),
            ),
        )


@router.post(
    "/roles/{role_id}/edit",
    response_class=HTMLResponse,
)
async def role_edit_submit(
    request: Request,
    role_id: int,
    csrf: str = Form(...),
    name: str = Form(""),
    code: str = Form(""),
    description: str = Form(""),
    permissions: list[str] = Form(default=[]),
):
    redirect = access_redirect(request, "roles.manage")
    if redirect:
        return redirect

    form_data = {
        "name": name,
        "code": code,
        "description": description,
    }

    with session_scope() as session:
        role = get_role(session, role_id)
        available_permissions = list_permissions(session)

        if role is None:
            return RedirectResponse("/admin/roles", status_code=303)

        errors: list[str] = []

        if not verify_csrf(request, csrf, "roles"):
            errors.append("La sesión del formulario expiró.")

        if not errors:
            try:
                role = update_role(
                    session,
                    role,
                    name=name,
                    code=code,
                    description=description,
                    permission_codes_value=permissions,
                )
                audit_request(
                    request,
                    session,
                    action="ROLE_UPDATE",
                    resource="role",
                    resource_id=role.id,
                    detail=(
                        f"Rol {role.name} actualizado con "
                        f"{len(role.permissions)} permisos."
                    ),
                )

                current_role_id = request.session.get("role_id")
                current_user_id = request.session.get("user_id")

                if (
                    current_role_id == role.id
                    and isinstance(current_user_id, int)
                ):
                    identity = get_identity(session, current_user_id)
                    if identity:
                        apply_identity_to_session(request, identity)

                return redirect_with_message(
                    "/admin/roles",
                    f"Rol {role.name} actualizado.",
                )

            except AccessServiceError as exc:
                errors.append(str(exc))
                audit_request(
                    request,
                    session,
                    action="ROLE_UPDATE",
                    resource="role",
                    resource_id=role.id,
                    detail=f"Actualización rechazada: {exc}",
                    success=False,
                )

        return templates.TemplateResponse(
            request=request,
            name="admin_role_form.html",
            status_code=400,
            context=context(
                request,
                current_page="roles",
                page_title=f"Editar {role.name}",
                page_subtitle="Nombre, descripción y permisos",
                mode="edit",
                role=role,
                permission_groups=permission_groups(
                    available_permissions
                ),
                selected_permissions=set(permissions),
                form_data=form_data,
                errors=errors,
                csrf_token=csrf_token(request, "roles"),
            ),
        )


@router.post("/roles/{role_id}/delete")
async def role_delete_submit(
    request: Request,
    role_id: int,
    csrf: str = Form(...),
):
    redirect = access_redirect(request, "roles.manage")
    if redirect:
        return redirect

    with session_scope() as session:
        role = get_role(session, role_id)

        if role is None:
            return RedirectResponse("/admin/roles", status_code=303)

        if not verify_csrf(request, csrf, "roles"):
            return redirect_with_message(
                "/admin/roles",
                "La sesión del formulario expiró.",
            )

        role_name = role.name

        try:
            delete_role(session, role)
            audit_request(
                request,
                session,
                action="ROLE_DELETE",
                resource="role",
                resource_id=role_id,
                detail=f"Rol {role_name} eliminado.",
            )

            return redirect_with_message(
                "/admin/roles",
                f"Rol {role_name} eliminado.",
            )

        except AccessServiceError as exc:
            audit_request(
                request,
                session,
                action="ROLE_DELETE",
                resource="role",
                resource_id=role_id,
                detail=f"Eliminación rechazada: {exc}",
                success=False,
            )

            return redirect_with_message(
                "/admin/roles",
                str(exc),
            )


@router.get(
    "/audit",
    response_class=HTMLResponse,
)
async def audit_page(
    request: Request,
    q: str = "",
    action: str = "",
    resource: str = "",
    success: str = "",
    date_from: str = "",
    date_to: str = "",
    page: int = 1,
):
    redirect = access_redirect(request, "audit.view")
    if redirect:
        return redirect

    with session_scope() as session:
        result = list_audit_events(
            session,
            page=page,
            page_size=settings.audit_page_size,
            query=q,
            action=action,
            resource=resource,
            success=success,
            date_from=date_from,
            date_to=date_to,
        )

        return templates.TemplateResponse(
            request=request,
            name="admin_audit.html",
            context=context(
                request,
                current_page="audit",
                page_title="Auditoría",
                page_subtitle=(
                    "Registro de accesos y cambios administrativos"
                ),
                query=q,
                selected_action=action,
                selected_resource=resource,
                selected_success=success,
                selected_date_from=date_from,
                selected_date_to=date_to,
                **result,
            ),
        )


def _csv_safe(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


@router.get("/audit/export.csv")
async def audit_export(
    request: Request,
    q: str = "",
    action: str = "",
    resource: str = "",
    success: str = "",
    date_from: str = "",
    date_to: str = "",
):
    redirect = access_redirect(request, "audit.view")
    if redirect:
        return redirect

    with session_scope() as session:
        try:
            events = export_audit_events(
                session,
                query=q,
                action=action,
                resource=resource,
                success=success,
                date_from=date_from,
                date_to=date_to,
            )
        except AccessServiceError as exc:
            return redirect_with_message(
                "/admin/audit",
                str(exc),
            )

        audit_request(
            request,
            session,
            action="AUDIT_EXPORT",
            resource="audit",
            detail=f"Exportación CSV con {len(events)} eventos.",
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "fecha_utc",
        "usuario",
        "accion",
        "recurso",
        "recurso_id",
        "resultado",
        "detalle",
        "ip",
        "agente",
    ])

    for event in events:
        writer.writerow([
            event.created_at.isoformat(),
            _csv_safe(event.username),
            _csv_safe(event.action),
            _csv_safe(event.resource),
            _csv_safe(event.resource_id),
            "correcto" if event.success else "fallido",
            _csv_safe(event.detail),
            _csv_safe(event.ip_address),
            _csv_safe(event.user_agent),
        ])

    filename = (
        "netdoc-auditoria-"
        + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        + ".csv"
    )
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-NetDoc-Export-Count": str(len(events)),
        },
    )
