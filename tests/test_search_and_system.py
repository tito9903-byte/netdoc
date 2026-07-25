import asyncio
import os
import tempfile
import unittest
from pathlib import Path

from argon2 import PasswordHasher


os.environ.setdefault("NETBOX_URL", "https://netbox.invalid")
os.environ.setdefault("NETBOX_TOKEN", "test-token")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    PasswordHasher().hash("AdminPassword123"),
)

from app.services.search_service import global_search
from app.services.system_service import (
    _read_meminfo,
    _read_network_totals,
    collect_system_health,
)


class FakeSearchClient:
    async def get_list(self, endpoint, params=None):
        payloads = {
            "/api/dcim/devices/": {
                "count": 1,
                "results": [{
                    "id": 10,
                    "name": "CORE-01",
                    "role": {"name": "Core"},
                    "device_type": {"model": "7280"},
                    "site": {"name": "SFM"},
                }],
            },
            "/api/dcim/interfaces/": {
                "count": 1,
                "results": [{
                    "id": 11,
                    "name": "Ethernet1",
                    "device": {"id": 10, "name": "CORE-01"},
                    "type": {"label": "10GBASE-X"},
                }],
            },
            "/api/dcim/racks/": {"count": 0, "results": []},
            "/api/dcim/sites/": {"count": 0, "results": []},
            "/api/dcim/cables/": {"count": 0, "results": []},
        }
        await asyncio.sleep(0)
        return payloads[endpoint]


class SearchServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_global_search_groups_results_and_links(self):
        result = await global_search("core", client=FakeSearchClient())

        self.assertTrue(result["searched"])
        self.assertEqual(2, result["total"])
        device_section = result["sections"][0]
        interface_section = result["sections"][1]
        self.assertEqual("/devices/10", device_section["results"][0]["url"])
        self.assertEqual("/devices/10", interface_section["results"][0]["url"])

    async def test_short_search_does_not_call_netbox(self):
        result = await global_search("x", client=FakeSearchClient())
        self.assertFalse(result["searched"])
        self.assertEqual([], result["sections"])


class SystemServiceTests(unittest.TestCase):
    def test_proc_parsers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            meminfo = root / "meminfo"
            meminfo.write_text(
                "MemTotal: 1000 kB\nMemAvailable: 400 kB\n"
            )
            netdev = root / "netdev"
            netdev.write_text(
                "header\nheader\n"
                "  lo: 10 0 0 0 0 0 0 0 10 0 0 0 0 0 0 0\n"
                "eth0: 100 0 0 0 0 0 0 0 200 0 0 0 0 0 0 0\n"
            )

            memory = _read_meminfo(meminfo)
            received, transmitted = _read_network_totals(netdev)

        self.assertEqual(1024000, memory["MemTotal"])
        self.assertEqual((100, 200), (received, transmitted))

    def test_collect_system_health_has_safe_read_only_metrics(self):
        health = collect_system_health(disk_path="/")
        self.assertIn("cpu", health)
        self.assertIn("memory", health)
        self.assertIn("disk", health)
        self.assertGreaterEqual(health["cpu"]["logical_count"], 1)
        self.assertGreaterEqual(health["disk"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
