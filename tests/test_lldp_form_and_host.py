from __future__ import annotations

from importlib import import_module
from pathlib import Path
import re
import unittest

from fastapi.routing import iter_route_contexts

from app.services.lldp_discovery_service import LldpDiscoveryService


class LldpExecutionFormTests(unittest.TestCase):
    def test_run_route_accepts_post_only(self):
        app = import_module("app.main").app
        matches = [
            context
            for context in iter_route_contexts(app.routes)
            if context.path == "/devices/{device_id}/lldp-discovery/run"
        ]

        self.assertEqual(1, len(matches))
        self.assertEqual({"POST"}, set(matches[0].methods or set()))

    def test_run_button_explicitly_forces_post_and_action(self):
        template = Path("app/templates/lldp_discovery.html").read_text(
            encoding="utf-8"
        )

        self.assertRegex(
            template,
            re.compile(
                r'<form\s+[^>]*id="lldp-run-form-\{\{ device_id \}\}"'
                r'[^>]*method="post"'
                r'[^>]*action="/devices/\{\{ device_id \}\}/lldp-discovery/run"',
                re.DOTALL,
            ),
        )
        self.assertIn('formmethod="post"', template)
        self.assertIn(
            'formaction="/devices/{{ device_id }}/lldp-discovery/run"',
            template,
        )


class LldpBareHostTests(unittest.TestCase):
    def test_primary_ipv4_mask_is_removed_before_ssh(self):
        service = object.__new__(LldpDiscoveryService)

        host = service._device_host({
            "primary_ip4": {"address": "192.168.10.39/32"},
        })

        self.assertEqual("192.168.10.39", host)
        self.assertNotIn("/", host)

    def test_primary_ipv6_mask_is_removed_before_ssh(self):
        service = object.__new__(LldpDiscoveryService)

        host = service._device_host({
            "primary_ip6": {"address": "2001:db8::39/128"},
        })

        self.assertEqual("2001:db8::39", host)
        self.assertNotIn("/", host)


if __name__ == "__main__":
    unittest.main()
