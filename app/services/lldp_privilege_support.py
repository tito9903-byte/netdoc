from __future__ import annotations

from typing import Any

from app.services.lldp_discovery_service import (
    LldpDiscoveryError,
    LldpDiscoveryService,
)


_ORIGINAL_RESOLVE_PROFILE = LldpDiscoveryService._resolve_profile
_PATCH_MARKER = "_netdoc_privilege_support_installed"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
        "si",
        "sí",
    }


def _resolve_profile_with_privilege(
    self: LldpDiscoveryService,
    device: dict[str, Any],
    spec: Any,
) -> dict[str, Any]:
    profile = dict(_ORIGINAL_RESOLVE_PROFILE(self, device, spec))
    use_enable = _as_bool(
        profile.get("use_enable", profile.get("enter_enable", False))
    )
    secret = str(profile.get("secret") or "")

    if use_enable and not secret:
        profile_key = str(profile.get("profile_key") or spec.key)
        raise LldpDiscoveryError(
            f"El perfil SSH {profile_key} solicita enable, pero no tiene secret configurado.",
            500,
        )

    profile["use_enable"] = use_enable
    profile["secret"] = secret
    return profile


def _collect_sync_with_privilege(
    self: LldpDiscoveryService,
    *,
    host: str,
    profile: dict[str, Any],
) -> Any:
    try:
        from netmiko import (
            ConnectHandler,
            NetmikoAuthenticationException,
            NetmikoTimeoutException,
        )
    except ImportError as exc:
        raise LldpDiscoveryError(
            "Netmiko no está instalado en el entorno de NetDoc.",
            500,
        ) from exc

    connection_args: dict[str, Any] = {
        "device_type": profile["device_type"],
        "host": host,
        "username": profile["username"],
        "password": profile.get("password") or "",
        "secret": profile.get("secret") or "",
        "port": profile["port"],
        "conn_timeout": self.settings.netdoc_ssh_connect_timeout,
        "auth_timeout": self.settings.netdoc_ssh_connect_timeout,
        "banner_timeout": self.settings.netdoc_ssh_connect_timeout,
        "fast_cli": False,
    }
    if profile.get("key_file"):
        connection_args.update({
            "use_keys": True,
            "key_file": profile["key_file"],
            "allow_agent": False,
        })

    connection = None
    try:
        connection = ConnectHandler(**connection_args)

        if _as_bool(profile.get("use_enable")):
            if not connection.check_enable_mode():
                connection.enable()
            if not connection.check_enable_mode():
                raise LldpDiscoveryError(
                    "NetDoc inició SSH, pero el equipo no permitió entrar al modo enable.",
                    502,
                )

        disable_paging = getattr(connection, "disable_paging", None)
        if callable(disable_paging):
            disable_paging()

        set_terminal_width = getattr(connection, "set_terminal_width", None)
        if callable(set_terminal_width):
            try:
                set_terminal_width(command="terminal width 511")
            except TypeError:
                set_terminal_width()

        return connection.send_command(
            profile["command"],
            use_textfsm=True,
            read_timeout=self.settings.netdoc_ssh_command_timeout,
        )
    except NetmikoAuthenticationException as exc:
        raise LldpDiscoveryError(
            "El equipo rechazó el usuario, la contraseña o el secret de enable.",
            502,
        ) from exc
    except NetmikoTimeoutException as exc:
        raise LldpDiscoveryError(
            f"No fue posible establecer SSH con {host} dentro del tiempo límite.",
            504,
        ) from exc
    except LldpDiscoveryError:
        raise
    except Exception as exc:
        raise LldpDiscoveryError(
            f"La consulta LLDP por SSH falló: {type(exc).__name__}: {exc}",
            502,
        ) from exc
    finally:
        if connection is not None:
            try:
                connection.disconnect()
            except Exception:
                pass


def install_lldp_privilege_support() -> None:
    """Instala soporte opcional de enable antes de registrar las rutas LLDP."""

    if getattr(LldpDiscoveryService, _PATCH_MARKER, False):
        return

    LldpDiscoveryService._resolve_profile = _resolve_profile_with_privilege
    LldpDiscoveryService._collect_sync = _collect_sync_with_privilege
    setattr(LldpDiscoveryService, _PATCH_MARKER, True)
