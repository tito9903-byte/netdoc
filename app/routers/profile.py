from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import (
    apply_identity_to_session,
    common_session_context,
    csrf_token,
    is_authenticated,
    request_client_data,
    verify_csrf,
)
from app.core.config import get_settings
from app.core.database import session_scope
from app.core.security import verify_password
from app.services.access_service import (
    AccessServiceError,
    get_identity,
    get_user,
    record_audit,
    set_user_password,
    update_user,
)


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


def _login_redirect(request: Request) -> RedirectResponse | None:
    if is_authenticated(request):
        return None

    next_url = request.url.path
    return RedirectResponse(
        url=f"/login?next={quote(next_url, safe='')}",
        status_code=303,
    )


def _context(request: Request, **extra: object) -> dict[str, object]:
    return {
        **common_session_context(request),
        "current_page": "profile",
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        **extra,
    }


def _redirect(message: str, *, error: bool = False) -> RedirectResponse:
    params = f"message={quote(message)}"
    if error:
        params += "&error=1"
    return RedirectResponse(f"/profile?{params}", status_code=303)


def _current_user_id(request: Request) -> int | None:
    value = request.session.get("user_id")
    return value if isinstance(value, int) else None


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    message: str = "",
    error: bool = False,
):
    redirect = _login_redirect(request)
    if redirect:
        return redirect

    user_id = _current_user_id(request)
    if user_id is None:
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    with session_scope() as session:
        user = get_user(session, user_id)
        if user is None or not user.is_active:
            request.session.clear()
            return RedirectResponse("/login", status_code=303)

        return templates.TemplateResponse(
            request=request,
            name="profile.html",
            context=_context(
                request,
                page_title="Mi perfil",
                page_subtitle="Datos personales y seguridad de la cuenta",
                user=user,
                message=message,
                message_is_error=error,
                profile_csrf=csrf_token(request, "profile"),
                password_csrf=csrf_token(request, "profile_password"),
            ),
        )


@router.post("/profile")
async def profile_update(
    request: Request,
    csrf: str = Form(...),
    full_name: str = Form(""),
    email: str = Form(""),
):
    redirect = _login_redirect(request)
    if redirect:
        return redirect

    if not verify_csrf(request, csrf, "profile"):
        return _redirect("La sesión del formulario expiró.", error=True)

    user_id = _current_user_id(request)
    if user_id is None:
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    ip_address, user_agent = request_client_data(request)

    with session_scope() as session:
        user = get_user(session, user_id)
        if user is None or not user.is_active:
            request.session.clear()
            return RedirectResponse("/login", status_code=303)

        try:
            user = update_user(
                session,
                user,
                username=user.username,
                full_name=full_name,
                email=email,
                role_id=user.role_id,
                is_active=True,
            )
            record_audit(
                session,
                action="PROFILE_UPDATE",
                resource="user",
                resource_id=user.id,
                user_id=user.id,
                username=user.username,
                detail="El usuario actualizó sus datos personales.",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            identity = get_identity(session, user.id)
        except AccessServiceError as exc:
            record_audit(
                session,
                action="PROFILE_UPDATE",
                resource="user",
                resource_id=user.id,
                user_id=user.id,
                username=user.username,
                detail=f"Actualización rechazada: {exc}",
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return _redirect(str(exc), error=True)

    if identity is not None:
        apply_identity_to_session(request, identity)

    return _redirect("Tu perfil fue actualizado.")


@router.post("/profile/password")
async def profile_password_update(
    request: Request,
    csrf: str = Form(...),
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    redirect = _login_redirect(request)
    if redirect:
        return redirect

    if not verify_csrf(request, csrf, "profile_password"):
        return _redirect("La sesión del formulario expiró.", error=True)

    if new_password != confirm_password:
        return _redirect("Las contraseñas nuevas no coinciden.", error=True)

    user_id = _current_user_id(request)
    if user_id is None:
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    ip_address, user_agent = request_client_data(request)

    with session_scope() as session:
        user = get_user(session, user_id)
        if user is None or not user.is_active:
            request.session.clear()
            return RedirectResponse("/login", status_code=303)

        if not verify_password(user.password_hash, current_password):
            record_audit(
                session,
                action="PROFILE_PASSWORD_CHANGE",
                resource="user",
                resource_id=user.id,
                user_id=user.id,
                username=user.username,
                detail="Cambio rechazado por contraseña actual incorrecta.",
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return _redirect("La contraseña actual no es correcta.", error=True)

        if verify_password(user.password_hash, new_password):
            return _redirect(
                "La contraseña nueva debe ser diferente de la actual.",
                error=True,
            )

        try:
            set_user_password(session, user, new_password)
            record_audit(
                session,
                action="PROFILE_PASSWORD_CHANGE",
                resource="user",
                resource_id=user.id,
                user_id=user.id,
                username=user.username,
                detail="El usuario cambió su propia contraseña.",
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except AccessServiceError as exc:
            record_audit(
                session,
                action="PROFILE_PASSWORD_CHANGE",
                resource="user",
                resource_id=user.id,
                user_id=user.id,
                username=user.username,
                detail=f"Cambio rechazado: {exc}",
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return _redirect(str(exc), error=True)

    return _redirect("Tu contraseña fue actualizada.")
