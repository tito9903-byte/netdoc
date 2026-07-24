from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.security import (
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.models.access import AuditEvent, Permission, Role, User


settings = get_settings()


PERMISSION_DEFINITIONS = [
    (
        "dashboard.view",
        "Ver dashboard",
        "Consultar indicadores y estado general.",
        "General",
    ),
    (
        "devices.view",
        "Ver dispositivos",
        "Consultar dispositivos e interfaces documentados.",
        "Inventario",
    ),
    (
        "devices.create",
        "Crear dispositivos",
        "Registrar equipos nuevos mediante NetBox.",
        "Inventario",
    ),
    (
        "connections.view",
        "Ver conexiones",
        "Consultar cables y extremos documentados.",
        "Conectividad",
    ),
    (
        "connections.create",
        "Crear conexiones",
        "Crear cables entre interfaces mediante NetBox.",
        "Conectividad",
    ),
    (
        "racks.view",
        "Ver racks",
        "Consultar racks y elevaciones 2D.",
        "Infraestructura",
    ),
    (
        "users.manage",
        "Gestionar usuarios",
        "Crear, editar, activar y restablecer usuarios.",
        "Administración",
    ),
    (
        "roles.manage",
        "Gestionar roles",
        "Crear y editar roles y permisos.",
        "Administración",
    ),
    (
        "audit.view",
        "Ver auditoría",
        "Consultar acciones administrativas y operativas.",
        "Administración",
    ),
]

VIEW_PERMISSIONS = {
    "dashboard.view",
    "devices.view",
    "connections.view",
    "racks.view",
}

OPERATOR_PERMISSIONS = VIEW_PERMISSIONS | {
    "devices.create",
    "connections.create",
}


class AccessServiceError(ValueError):
    pass


@dataclass(frozen=True)
class AuthenticatedIdentity:
    id: int
    username: str
    full_name: str
    role_id: int
    role_name: str
    role_code: str
    permissions: tuple[str, ...]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_username(value: str) -> str:
    return value.strip().lower()


def normalize_email(value: str | None) -> str | None:
    email = (value or "").strip().lower()
    return email or None


def normalize_role_code(value: str) -> str:
    code = value.strip().lower()
    code = re.sub(r"[^a-z0-9]+", "_", code)
    return code.strip("_")


def permission_codes(role: Role) -> set[str]:
    return {permission.code for permission in role.permissions}


def identity_from_user(user: User) -> AuthenticatedIdentity:
    return AuthenticatedIdentity(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role_id=user.role.id,
        role_name=user.role.name,
        role_code=user.role.code,
        permissions=tuple(sorted(permission_codes(user.role))),
    )


def seed_access_control(session: Session) -> None:
    permissions_by_code: dict[str, Permission] = {}

    for code, name, description, category in PERMISSION_DEFINITIONS:
        permission = session.scalar(
            select(Permission).where(Permission.code == code)
        )

        if permission is None:
            permission = Permission(
                code=code,
                name=name,
                description=description,
                category=category,
            )
            session.add(permission)
        else:
            permission.name = name
            permission.description = description
            permission.category = category

        permissions_by_code[code] = permission

    session.flush()

    role_definitions = [
        (
            "administrador",
            "Administrador",
            "Acceso completo a NetDoc.",
            set(permissions_by_code),
        ),
        (
            "operador",
            "Operador",
            "Consulta y operaciones guiadas sobre NetBox.",
            OPERATOR_PERMISSIONS,
        ),
        (
            "consulta",
            "Consulta",
            "Acceso de solo lectura al inventario.",
            VIEW_PERMISSIONS,
        ),
    ]

    roles_by_code: dict[str, Role] = {}

    for code, name, description, codes in role_definitions:
        role = session.scalar(select(Role).where(Role.code == code))

        if role is None:
            role = Role(
                code=code,
                name=name,
                description=description,
                is_system=True,
            )
            session.add(role)
            session.flush()

        role.name = name
        role.description = description
        role.is_system = True
        role.permissions = [
            permissions_by_code[item]
            for item in sorted(codes)
            if item in permissions_by_code
        ]
        roles_by_code[code] = role

    admin_username = normalize_username(settings.admin_username)
    admin = session.scalar(
        select(User).where(func.lower(User.username) == admin_username)
    )

    if admin is None:
        admin = User(
            username=admin_username,
            full_name="Administrador de NetDoc",
            email=None,
            password_hash=settings.admin_password_hash,
            is_active=True,
            role=roles_by_code["administrador"],
        )
        session.add(admin)


def authenticate_user(
    session: Session,
    username: str,
    password: str,
) -> AuthenticatedIdentity | None:
    normalized = normalize_username(username)

    user = session.scalar(
        select(User)
        .options(
            selectinload(User.role).selectinload(Role.permissions)
        )
        .where(func.lower(User.username) == normalized)
    )

    if user is None or not user.is_active:
        return None

    if not verify_password(user.password_hash, password):
        return None

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        user.password_changed_at = utc_now()

    user.last_login_at = utc_now()
    session.flush()

    return identity_from_user(user)


def get_identity(
    session: Session,
    user_id: int,
) -> AuthenticatedIdentity | None:
    user = session.scalar(
        select(User)
        .options(
            selectinload(User.role).selectinload(Role.permissions)
        )
        .where(User.id == user_id)
    )

    if user is None or not user.is_active:
        return None

    return identity_from_user(user)


def list_users(session: Session) -> list[User]:
    return list(
        session.scalars(
            select(User)
            .options(
                selectinload(User.role).selectinload(Role.permissions)
            )
            .order_by(User.username)
        ).all()
    )


def get_user(session: Session, user_id: int) -> User | None:
    return session.scalar(
        select(User)
        .options(
            selectinload(User.role).selectinload(Role.permissions)
        )
        .where(User.id == user_id)
    )


def _username_exists(
    session: Session,
    username: str,
    exclude_user_id: int | None = None,
) -> bool:
    query = select(User.id).where(
        func.lower(User.username) == normalize_username(username)
    )

    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)

    return session.scalar(query) is not None


def _email_exists(
    session: Session,
    email: str | None,
    exclude_user_id: int | None = None,
) -> bool:
    normalized = normalize_email(email)

    if normalized is None:
        return False

    query = select(User.id).where(
        func.lower(User.email) == normalized
    )

    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)

    return session.scalar(query) is not None


def validate_password(password: str) -> None:
    if len(password) < 10:
        raise AccessServiceError(
            "La contraseña debe tener al menos 10 caracteres."
        )

    if password.lower() == password or password.upper() == password:
        raise AccessServiceError(
            "La contraseña debe combinar mayúsculas y minúsculas."
        )

    if not any(character.isdigit() for character in password):
        raise AccessServiceError(
            "La contraseña debe incluir al menos un número."
        )


def create_user(
    session: Session,
    *,
    username: str,
    full_name: str,
    email: str | None,
    password: str,
    role_id: int,
    is_active: bool = True,
) -> User:
    normalized_username = normalize_username(username)
    normalized_email = normalize_email(email)

    if not normalized_username:
        raise AccessServiceError("El nombre de usuario es obligatorio.")

    if len(normalized_username) < 3:
        raise AccessServiceError(
            "El nombre de usuario debe tener al menos 3 caracteres."
        )

    if not re.fullmatch(r"[a-z0-9._-]+", normalized_username):
        raise AccessServiceError(
            "El usuario solo puede contener letras, números, punto, guion y guion bajo."
        )

    if _username_exists(session, normalized_username):
        raise AccessServiceError("Ya existe un usuario con ese nombre.")

    if _email_exists(session, normalized_email):
        raise AccessServiceError("Ya existe un usuario con ese correo.")

    role = session.get(Role, role_id)
    if role is None:
        raise AccessServiceError("El rol seleccionado no existe.")

    validate_password(password)

    user = User(
        username=normalized_username,
        full_name=full_name.strip(),
        email=normalized_email,
        password_hash=hash_password(password),
        is_active=is_active,
        role=role,
    )
    session.add(user)
    session.flush()
    return user


def update_user(
    session: Session,
    user: User,
    *,
    username: str,
    full_name: str,
    email: str | None,
    role_id: int,
    is_active: bool,
) -> User:
    normalized_username = normalize_username(username)
    normalized_email = normalize_email(email)

    if not normalized_username:
        raise AccessServiceError("El nombre de usuario es obligatorio.")

    if _username_exists(session, normalized_username, user.id):
        raise AccessServiceError("Ya existe un usuario con ese nombre.")

    if _email_exists(session, normalized_email, user.id):
        raise AccessServiceError("Ya existe un usuario con ese correo.")

    role = session.get(Role, role_id)
    if role is None:
        raise AccessServiceError("El rol seleccionado no existe.")

    user.username = normalized_username
    user.full_name = full_name.strip()
    user.email = normalized_email
    user.role = role
    user.is_active = is_active
    user.updated_at = utc_now()
    session.flush()
    return user


def set_user_password(
    session: Session,
    user: User,
    password: str,
) -> None:
    validate_password(password)
    user.password_hash = hash_password(password)
    user.password_changed_at = utc_now()
    user.updated_at = utc_now()
    session.flush()


def count_active_admins(session: Session) -> int:
    return int(
        session.scalar(
            select(func.count(User.id))
            .join(Role)
            .where(
                User.is_active.is_(True),
                Role.code == "administrador",
            )
        )
        or 0
    )


def list_roles(session: Session) -> list[Role]:
    return list(
        session.scalars(
            select(Role)
            .options(
                selectinload(Role.permissions),
                selectinload(Role.users),
            )
            .order_by(Role.name)
        ).all()
    )


def get_role(session: Session, role_id: int) -> Role | None:
    return session.scalar(
        select(Role)
        .options(
            selectinload(Role.permissions),
            selectinload(Role.users),
        )
        .where(Role.id == role_id)
    )


def list_permissions(session: Session) -> list[Permission]:
    return list(
        session.scalars(
            select(Permission).order_by(
                Permission.category,
                Permission.name,
            )
        ).all()
    )


def _role_code_exists(
    session: Session,
    code: str,
    exclude_role_id: int | None = None,
) -> bool:
    query = select(Role.id).where(Role.code == code)

    if exclude_role_id is not None:
        query = query.where(Role.id != exclude_role_id)

    return session.scalar(query) is not None


def _role_name_exists(
    session: Session,
    name: str,
    exclude_role_id: int | None = None,
) -> bool:
    query = select(Role.id).where(
        func.lower(Role.name) == name.strip().lower()
    )

    if exclude_role_id is not None:
        query = query.where(Role.id != exclude_role_id)

    return session.scalar(query) is not None


def _resolve_permissions(
    session: Session,
    codes: list[str],
) -> list[Permission]:
    selected_codes = sorted(set(codes))

    if not selected_codes:
        return []

    permissions = list(
        session.scalars(
            select(Permission).where(
                Permission.code.in_(selected_codes)
            )
        ).all()
    )

    if len(permissions) != len(selected_codes):
        raise AccessServiceError(
            "Uno o más permisos seleccionados no son válidos."
        )

    return permissions


def create_role(
    session: Session,
    *,
    name: str,
    code: str,
    description: str,
    permission_codes_value: list[str],
) -> Role:
    clean_name = name.strip()
    clean_code = normalize_role_code(code or name)

    if not clean_name:
        raise AccessServiceError("El nombre del rol es obligatorio.")

    if not clean_code:
        raise AccessServiceError("El código del rol no es válido.")

    if _role_name_exists(session, clean_name):
        raise AccessServiceError("Ya existe un rol con ese nombre.")

    if _role_code_exists(session, clean_code):
        raise AccessServiceError("Ya existe un rol con ese código.")

    role = Role(
        name=clean_name,
        code=clean_code,
        description=description.strip(),
        is_system=False,
        permissions=_resolve_permissions(
            session,
            permission_codes_value,
        ),
    )
    session.add(role)
    session.flush()
    return role


def update_role(
    session: Session,
    role: Role,
    *,
    name: str,
    code: str,
    description: str,
    permission_codes_value: list[str],
) -> Role:
    clean_name = name.strip()
    clean_code = (
        role.code
        if role.is_system
        else normalize_role_code(code or name)
    )

    if not clean_name:
        raise AccessServiceError("El nombre del rol es obligatorio.")

    if _role_name_exists(session, clean_name, role.id):
        raise AccessServiceError("Ya existe un rol con ese nombre.")

    if _role_code_exists(session, clean_code, role.id):
        raise AccessServiceError("Ya existe un rol con ese código.")

    selected = _resolve_permissions(
        session,
        permission_codes_value,
    )

    if role.code == "administrador":
        selected = list_permissions(session)

    role.name = clean_name
    role.code = clean_code
    role.description = description.strip()
    role.permissions = selected
    role.updated_at = utc_now()
    session.flush()
    return role


def delete_role(session: Session, role: Role) -> None:
    if role.is_system:
        raise AccessServiceError(
            "Los roles del sistema no se pueden eliminar."
        )

    if role.users:
        raise AccessServiceError(
            "No se puede eliminar un rol que tiene usuarios asignados."
        )

    session.delete(role)
    session.flush()


def record_audit(
    session: Session,
    *,
    action: str,
    resource: str,
    username: str,
    user_id: int | None = None,
    resource_id: str | int | None = None,
    detail: str = "",
    success: bool = True,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        action=action,
        resource=resource,
        username=username or "sistema",
        user_id=user_id,
        resource_id=(
            str(resource_id)
            if resource_id is not None
            else None
        ),
        detail=detail[:4000],
        success=success,
        ip_address=(ip_address or "")[:64] or None,
        user_agent=(user_agent or "")[:512] or None,
    )
    session.add(event)
    session.flush()
    return event


def list_audit_events(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 50,
    query: str = "",
    action: str = "",
    success: str = "",
) -> dict[str, object]:
    page = max(1, page)
    page_size = min(max(page_size, 10), 100)

    filters = []

    if query.strip():
        pattern = f"%{query.strip()}%"
        filters.append(
            (
                AuditEvent.username.ilike(pattern)
                | AuditEvent.resource.ilike(pattern)
                | AuditEvent.detail.ilike(pattern)
                | AuditEvent.resource_id.ilike(pattern)
            )
        )

    if action.strip():
        filters.append(AuditEvent.action == action.strip())

    if success == "true":
        filters.append(AuditEvent.success.is_(True))
    elif success == "false":
        filters.append(AuditEvent.success.is_(False))

    total = int(
        session.scalar(
            select(func.count(AuditEvent.id)).where(*filters)
        )
        or 0
    )

    events = list(
        session.scalars(
            select(AuditEvent)
            .where(*filters)
            .order_by(AuditEvent.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )

    total_pages = max(1, ceil(total / page_size))

    actions = list(
        session.scalars(
            select(AuditEvent.action)
            .distinct()
            .order_by(AuditEvent.action)
        ).all()
    )

    return {
        "events": events,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "actions": actions,
    }
