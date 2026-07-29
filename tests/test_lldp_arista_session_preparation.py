from __future__ import annotations

import inspect
import unittest

from app.services import lldp_privilege_support
from app.services.lldp_discovery_service import LldpDiscoveryService


class AristaSessionPreparationTests(unittest.TestCase):
    def test_arista_connection_uses_local_session_preparation_without_width(self):
        source = inspect.getsource(lldp_privilege_support._open_connection)

        self.assertIn("class NetDocAristaSSH(AristaSSH)", source)
        self.assertIn('device_type != "arista_eos"', source)
        self.assertIn('command="terminal length 0"', source)
        self.assertIn("self.set_base_prompt()", source)
        self.assertNotIn("set_terminal_width(", source)
        self.assertNotIn('command="terminal width 511"', source)

    def test_installer_replaces_a_previous_collector_revision(self):
        original = LldpDiscoveryService._collect_sync

        try:
            LldpDiscoveryService._collect_sync = object()
            setattr(
                LldpDiscoveryService,
                "_netdoc_privilege_support_revision",
                "revision-antigua",
            )

            lldp_privilege_support.install_lldp_privilege_support()

            self.assertIs(
                LldpDiscoveryService._collect_sync,
                lldp_privilege_support._collect_sync_with_privilege,
            )
            self.assertEqual(
                lldp_privilege_support.LLDP_COLLECTOR_REVISION,
                getattr(
                    LldpDiscoveryService,
                    "_netdoc_privilege_support_revision",
                ),
            )
        finally:
            LldpDiscoveryService._collect_sync = original
            lldp_privilege_support.install_lldp_privilege_support()


if __name__ == "__main__":
    unittest.main()
