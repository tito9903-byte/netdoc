from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from app.services.lldp_discovery_service import LldpDiscoveryService


class LldpConfigurationTests(unittest.IsolatedAsyncioTestCase):
    async def test_device_context_explains_missing_profile_without_failing(self):
        service = object.__new__(LldpDiscoveryService)
        service.settings = SimpleNamespace(netdoc_ssh_profiles_json="{}")
        service.client = SimpleNamespace(
            request=AsyncMock(return_value={
                "id": 10,
                "name": "ARISTA-CORE-01",
                "primary_ip4": {"address": "192.168.10.10/24"},
                "platform": {"slug": "arista_eos"},
                "device_type": {
                    "manufacturer": {"name": "Arista"},
                },
                "custom_fields": {},
            })
        )

        result = await service.device_context(10)

        self.assertEqual("192.168.10.10", result["host"])
        self.assertEqual("arista_eos", result["profile_key"])
        self.assertFalse(result["profile_configured"])
        self.assertIn("no tiene usuario", result["profile_error"])
        self.assertEqual("show lldp neighbors detail", result["command"])


if __name__ == "__main__":
    unittest.main()
