from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.services.lldp_discovery_service import (
    LldpDiscoveryError,
    LldpDiscoveryService,
    PlatformSpec,
)
from app.services.lldp_privilege_support import (
    _as_bool,
    _collect_sync_with_privilege,
    _resolve_profile_with_privilege,
    install_lldp_privilege_support,
)


class LldpEnableProfileTests(unittest.TestCase):
    def test_boolean_parser_accepts_environment_friendly_values(self):
        for value in (True, 1, "true", "YES", "on", "sí"):
            with self.subTest(value=value):
                self.assertTrue(_as_bool(value))
        for value in (False, 0, "false", "no", "off", ""):
            with self.subTest(value=value):
                self.assertFalse(_as_bool(value))

    def test_profile_requires_secret_when_enable_is_requested(self):
        service = object.__new__(LldpDiscoveryService)
        service._profiles = lambda: {
            "arista_eos": {
                "username": "netdoc-read",
                "password": "login-password",
                "use_enable": True,
            }
        }
        spec = PlatformSpec(
            key="arista_eos",
            netmiko_type="arista_eos",
            command="show lldp neighbors detail",
            label="Arista EOS",
        )

        with self.assertRaises(LldpDiscoveryError) as raised:
            _resolve_profile_with_privilege(service, {}, spec)

        self.assertIn("no tiene secret", raised.exception.message)

    def test_profile_keeps_distinct_login_and_enable_secrets(self):
        service = object.__new__(LldpDiscoveryService)
        service._profiles = lambda: {
            "arista_eos": {
                "username": "netdoc-read",
                "password": "login-password",
                "secret": "enable-password",
                "use_enable": "true",
            }
        }
        spec = PlatformSpec(
            key="arista_eos",
            netmiko_type="arista_eos",
            command="show lldp neighbors detail",
            label="Arista EOS",
        )

        profile = _resolve_profile_with_privilege(service, {}, spec)

        self.assertTrue(profile["use_enable"])
        self.assertEqual("login-password", profile["password"])
        self.assertEqual("enable-password", profile["secret"])


class LldpEnableExecutionTests(unittest.TestCase):
    def _run_collection(self, *, initially_enabled: bool):
        events: list[str] = []

        class FakeConnection:
            def __init__(self):
                self.enabled = initially_enabled

            def check_enable_mode(self):
                events.append("check_enable")
                return self.enabled

            def enable(self):
                events.append("enable")
                self.enabled = True

            def send_command(self, command, **kwargs):
                events.append(f"command:{command}")
                return [{
                    "local_interface": "Ethernet1",
                    "neighbor": "SW-CORE-02",
                    "neighbor_interface": "Ethernet49",
                }]

            def disconnect(self):
                events.append("disconnect")

        service = object.__new__(LldpDiscoveryService)
        service.settings = SimpleNamespace(
            netdoc_ssh_connect_timeout=10,
            netdoc_ssh_command_timeout=30,
        )
        profile = {
            "device_type": "arista_eos",
            "username": "netdoc-read",
            "password": "login-password",
            "secret": "enable-password",
            "port": 22,
            "command": "show lldp neighbors detail",
            "use_enable": True,
            "key_file": "",
        }

        connection = FakeConnection()
        with patch(
            "app.services.lldp_privilege_support._open_connection",
            return_value=connection,
        ) as open_connection:
            result = _collect_sync_with_privilege(
                service,
                host="192.0.2.10",
                profile=profile,
            )

        open_connection.assert_called_once()
        call_kwargs = open_connection.call_args.kwargs
        self.assertEqual("arista_eos", call_kwargs["device_type"])
        self.assertEqual("192.0.2.10", call_kwargs["connection_args"]["host"])
        self.assertEqual(
            "enable-password",
            call_kwargs["connection_args"]["secret"],
        )

        return events, result

    def test_runs_enable_before_lldp_when_prompt_is_unprivileged(self):
        events, result = self._run_collection(initially_enabled=False)

        self.assertEqual(
            [
                "check_enable",
                "enable",
                "check_enable",
                "command:show lldp neighbors detail",
                "disconnect",
            ],
            events,
        )
        self.assertEqual("Ethernet1", result[0]["local_interface"])

    def test_does_not_repeat_enable_when_login_is_already_privileged(self):
        events, _result = self._run_collection(initially_enabled=True)

        self.assertNotIn("enable", events)
        self.assertLess(
            events.index("check_enable"),
            events.index("command:show lldp neighbors detail"),
        )

    def test_installation_is_idempotent(self):
        install_lldp_privilege_support()
        first_collect = LldpDiscoveryService._collect_sync
        install_lldp_privilege_support()
        self.assertIs(first_collect, LldpDiscoveryService._collect_sync)


if __name__ == "__main__":
    unittest.main()
