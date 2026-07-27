from __future__ import annotations

from typing import Any

from app.services.lldp_discovery_service import (
    LldpDiscoveryError,
    LldpDiscoveryService,
)


_ORIGINAL_RESOLVE_PROFILE = LldpDiscoveryService._resolve_profile
_PATCH_MARKER = "_netdoc_privilege_support_revision"
LLDP_COLLECTOR_REVISION = "20260727-arista-session-no-width-v1"


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


def _open_connection(
    *,
    connection_args: dict[str, Any],
    device_type: str,
):
    """Abre SSH evitando la preparación incompatible de Arista EOS antiguo.

    Netmiko ejecuta la preparación de sesión dentro del constructor. Su driver
    estándar de Arista intenta cambiar el ancho del terminal y espera una frase
    específica antes de devolver el objeto conectado. Algunas versiones de EOS
    aceptan el comando, pero no imprimen esa frase; la conexión termina entonces
    con ReadTimeout antes de que NetDoc pueda enviar el comando LLDP.

    Para Arista usamos una subclase local que conserva la detección del prompt y
    desactiva el paginador, pero omite por completo el cambio de ancho. Los demás
    fabricantes continúan usando ConnectHandler sin modificaciones.
    """

    try:
        from netmiko import ConnectHandler
        from netmiko.arista.arista import AristaSSH
    except ImportError as exc:
        raise LldpDiscoveryError(
            "Netmiko no está instalado en el entorno de NetDoc.",
            500,
        ) from exc

    if device_type != "arista_eos":
        return ConnectHandler(**connection_args)

    class NetDocAristaSSH(AristaSSH):
        def session_preparation(self) -> None:
            self.ansi_escape_codes = True
            self._test_channel_read(pattern=self.prompt_pattern)
            self.set_base_prompt()
            self.disable_paging(
                command="terminal length 0",
                cmd_verify=False,
            )

    return NetDocAristaSSH(**connection_args)


def _collect_sync_with_privilege(
    self: LldpDiscoveryService,
    *,
    host: str,
    profile: dict[str, Any],
) -> Any:
    try:
        from netmiko import (
            NetmikoAuthenticationException,
            NetmikoTimeoutException,
        )
    except ImportError as exc:
        raise LldpDiscoveryError(
            "Netmiko no está instalado en el entorno de NetDoc.",
            500,
        ) from exc

    device_type = str(profile.get("device_type") or "")
    connection_args: dict[str, Any] = {
        "device_type": device_type,
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
        connection = _open_connection(
            connection_args=connection_args,
            device_type=device_type,
        )

        if _as_bool(profile.get("use_enable")):
            if not connection.check_enable_mode():
                connection.enable()
            if not connection.check_enable_mode():
                raise LldpDiscoveryError(
                    "NetDoc inició SSH, pero el equipo no permitió entrar al modo enable.",
                    502,
                )

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
    """Instala siempre la revisión vigente del colector SSH LLDP."""

    # No se corta por un marcador booleano. En desarrollo puede existir un proceso
    # recargado que conserve una revisión anterior de la función en la clase; la
    # asignación incondicional garantiza que el colector actual la reemplace.
    LldpDiscoveryService._resolve_profile = _resolve_profile_with_privilege
    LldpDiscoveryService._collect_sync = _collect_sync_with_privilege
    setattr(
        LldpDiscoveryService,
        _PATCH_MARKER,
        LLDP_COLLECTOR_REVISION,
    )
