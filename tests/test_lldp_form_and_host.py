from __future__ import annotations

from importlib import import_module
from pathlib import Path
import re
import unittest

from fastapi.routing import iter_route_contexts

from app.services.lldp_discovery_service import LldpDiscoveryService


class LldpExecutionFormTests(unittest.TestCase):
    def test_run_route_posts_discovery_and_redirects_accidental_gets(self):
        app = import_module("app.main").app
        matches = [
            context
            for context in iter_route_contexts(app.routes)
            if context.path == "/devices/{device_id}/lldp-discovery/run"
        ]

        methods = set().union(*(set(item.methods or set()) for item in matches))
        self.assertEqual({"GET", "POST"}, methods)
        self.assertEqual(2, len(matches))

    def test_run_button_uses_explicit_javascript_post(self):
        template = Path("app/templates/lldp_discovery.html").read_text(
            encoding="utf-8"
        )
        script = Path("app/static/js/lldp_discovery.js").read_text(
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
        self.assertIn('type="button"', template)
        self.assertIn("data-lldp-run-button", template)
        self.assertIn("js/lldp_discovery.js", template)
        self.assertIn('method: "POST"', script)
        self.assertIn("new FormData(form)", script)
        self.assertIn('button.addEventListener("click", executeDiscovery)', script)
        self.assertNotIn('window.location.assign(form.action)', script)

    def test_arista_collection_does_not_call_terminal_width(self):
        source = Path("app/services/lldp_privilege_support.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("set_terminal_width(", source)
        self.assertIn("self.disable_paging(", source)
        self.assertIn('command="terminal length 0"', source)

    def test_accidental_get_is_visible_and_device_navigation_stays_active(self):
        redirect_source = Path("app/routers/lldp_run_redirect.py").read_text(
            encoding="utf-8"
        )
        discovery_source = Path("app/routers/lldp_discovery.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('{"run_method": "get"}', redirect_source)
        self.assertIn('run_method: str = ""', discovery_source)
        self.assertIn("La ejecución LLDP no se inició", discovery_source)
        self.assertIn('"current_page": "devices"', discovery_source)


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
