import secrets
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from app.services.access_service import AuthenticatedIdentity


def is_authenticated(request: Request) -> bool:
    return (
        request.session.get("authenticated") is True
        and isinstance(request.session.get("user_id"), int)
        and bool(request.session.get("username"))
    )


def session_permissions(request: Request) -> set[str]:
    value = request.session.get("permissions", [])

    if not isinstance(value, list):
        return set()

    return {
        item
        for item in value
        if isinstance(item, str)
    }


def has_permission(request: Request, permission: str) -> bool:
    return (
        is_authenticated(request)
        and permission in session_permissions(request)
    )


def refresh_identity_in_session(
    request: Request,
    identity: AuthenticatedIdentity,
) -> None:
    request.session["authenticated"] = True
    request.session["user_id"] = identity.id
    request.session["username"] = identity.username
    request.session["full_name"] = identity.full_name
    request.session["role_id"] = identity.role_id
    request.session["role_name"] = identity.role_name
    request.session["role_code"] = identity.role_code
    request.session["permissions"] = list(identity.permissions)


def apply_identity_to_session(
    request: Request,
    identity: AuthenticatedIdentity,
) -> None:
    request.session.clear()
    refresh_identity_in_session(request, identity)


def access_redirect(
    request: Request,
    permission: str,
) -> RedirectResponse | None:
    if not is_authenticated(request):
        next_url = request.url.path

        if request.url.query:
            next_url = f"{next_url}?{request.url.query}"

        return RedirectResponse(
            url=f"/login?next={quote(next_url, safe='')}",
            status_code=303,
        )

    if not has_permission(request, permission):
        return RedirectResponse(
            url="/forbidden",
            status_code=303,
        )

    return None


def api_access_response(
    request: Request,
    permission: str,
) -> JSONResponse | None:
    if not is_authenticated(request):
        return JSONResponse(
            status_code=401,
            content={
                "ok": False,
                "error": "Debes iniciar sesión.",
            },
        )

    if not has_permission(request, permission):
        return JSONResponse(
            status_code=403,
            content={
                "ok": False,
                "error": "No tienes permiso para realizar esta acción.",
            },
        )

    return None


def common_session_context(request: Request) -> dict[str, object]:
    return {
        "current_user": request.session.get("username", ""),
        "current_user_name": request.session.get("full_name", ""),
        "current_role": request.session.get("role_name", ""),
        "current_permissions": session_permissions(request),
    }


def csrf_token(
    request: Request,
    namespace: str = "default",
) -> str:
    key = f"csrf_{namespace}"
    token = request.session.get(key)

    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        request.session[key] = token

    return token


def verify_csrf(
    request: Request,
    submitted: str,
    namespace: str = "default",
) -> bool:
    stored = request.session.get(f"csrf_{namespace}")

    return (
        isinstance(stored, str)
        and isinstance(submitted, str)
        and bool(stored)
        and secrets.compare_digest(stored, submitted)
    )


def request_client_data(
    request: Request,
) -> tuple[str | None, str | None]:
    ip_address = (
        request.client.host
        if request.client is not None
        else None
    )
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


class PermissionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: StarletteRequest,
        call_next,
    ) -> Response:
        permission = self._required_permission(
            request.url.path,
            request.method,
        )

        if permission is None:
            return await call_next(request)

        if not is_authenticated(request):
            return self._authentication_required(request)

        identity = self._load_identity(request)

        if identity is None:
            request.session.clear()
            return self._authentication_required(request)

        refresh_identity_in_session(request, identity)

        if permission and not has_permission(request, permission):
            if request.url.path.startswith("/api/"):
                return JSONResponse(
                    status_code=403,
                    content={
                        "ok": False,
                        "error": (
                            "No tienes permiso para realizar "
                            "esta acción."
                        ),
                    },
                )

            return RedirectResponse(
                url="/forbidden",
                status_code=303,
            )

        response = await call_next(request)
        self._audit_mutation(request, response)
        return response

    @staticmethod
    def _authentication_required(
        request: StarletteRequest,
    ) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=401,
                content={
                    "ok": False,
                    "error": "Debes iniciar sesión.",
                },
            )

        next_url = request.url.path
        if request.url.query:
            next_url = f"{next_url}?{request.url.query}"

        return RedirectResponse(
            url=f"/login?next={quote(next_url, safe='')}",
            status_code=303,
        )

    @staticmethod
    def _load_identity(
        request: StarletteRequest,
    ) -> AuthenticatedIdentity | None:
        user_id = request.session.get("user_id")

        if not isinstance(user_id, int):
            return None

        try:
            from app.core.database import session_scope
            from app.services.access_service import get_identity

            with session_scope() as session:
                return get_identity(session, user_id)
        except Exception:
            return None

    @staticmethod
    def _audit_mutation(
        request: StarletteRequest,
        response: Response,
    ) -> None:
        mutation = {
            ("POST", "/devices/actions/new"): (
                "DEVICE_CREATE_SUBMIT",
                "device",
            ),
            ("POST", "/connections"): (
                "CONNECTION_CREATE_SUBMIT",
                "connection",
            ),
        }.get((request.method.upper(), request.url.path))

        if mutation is None:
            return

        try:
            from app.core.database import session_scope
            from app.services.access_service import record_audit

            user_id = request.session.get("user_id")
            username = str(
                request.session.get("username") or "desconocido"
            )
            ip_address, user_agent = request_client_data(request)

            with session_scope() as session:
                record_audit(
                    session,
                    action=mutation[0],
                    resource=mutation[1],
                    user_id=(
                        user_id
                        if isinstance(user_id, int)
                        else None
                    ),
                    username=username,
                    detail=(
                        f"Solicitud {request.method} "
                        f"{request.url.path}; "
                        f"HTTP {response.status_code}."
                    ),
                    success=(
                        200 <= response.status_code < 400
                    ),
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
        except Exception:
            return

    @staticmethod
    def _required_permission(
        path: str,
        method: str,
    ) -> str | None:
        if (
            path == "/health"
            or path == "/login"
            or path.startswith("/static/")
            or path == "/favicon.ico"
        ):
            return None

        if path in {"/logout", "/forbidden"}:
            return ""

        if path == "/" or path in {
            "/netbox/status",
            "/api/dashboard",
        }:
            return "dashboard.view"

        if path.startswith("/profile"):
            return ""

        if path == "/search" or path.startswith("/api/search"):
            return "search.view"

        if path == "/system" or path.startswith("/api/system"):
            return "system.view"

        if path.startswith("/admin/users"):
            return "users.manage"

        if path.startswith("/admin/roles"):
            return "roles.manage"

        if path.startswith("/admin/audit"):
            return "audit.view"

        if path.startswith("/sites/actions/"):
            return "sites.manage"

        if path.startswith("/sites/") and (
            path.endswith("/edit") or path.endswith("/deactivate")
        ):
            return "sites.manage"

        if path.startswith("/sites"):
            return "sites.view"

        if path.startswith("/devices/actions/new"):
            return "devices.create"

        if path.startswith("/devices"):
            return "devices.view"

        if path.startswith("/api/connections"):
            return "connections.view"

        if path == "/connections" and method.upper() == "POST":
            return "connections.create"

        if path.startswith("/connections"):
            return "connections.view"

        if path.startswith("/racks"):
            return "racks.view"

        return ""
