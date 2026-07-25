from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from app.services.device_type_service import DeviceTypeService
from app.services.ipam_service import IPAMService
from app.services.netbox_client import NetBoxClient


class DashboardPerformanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        NetBoxClient._dashboard_cache = None

    @patch.object(
        NetBoxClient,
        "_fetch_recent_devices",
        new_callable=AsyncMock,
        return_value=[{"id": 9, "name": "OLT-SMN-01"}],
    )
    @patch.object(
        NetBoxClient,
        "count",
        new_callable=AsyncMock,
        side_effect=[1, 2, 3, 4, 5],
    )
    async def test_dashboard_summary_preloads_recent_and_reuses_cache(
        self,
        count,
        fetch_recent,
    ):
        client = NetBoxClient()

        first_summary = await client.dashboard_summary()
        recent = await client.recent_devices(limit=8)
        second_summary = await client.dashboard_summary()

        self.assertEqual(5, count.await_count)
        fetch_recent.assert_awaited_once_with(8)
        self.assertEqual("OLT-SMN-01", recent[0]["name"])
        self.assertEqual(first_summary, second_summary)


class IPAMPerformanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        IPAMService._inventory_cache = None
        IPAMService._overview_cache.clear()

    async def test_overview_starts_prefix_roles_and_inventory_together(self):
        service = IPAMService()
        started: set[str] = set()
        release = asyncio.Event()

        async def prefixes(*args, **kwargs):
            started.add("prefixes")
            await release.wait()
            return []

        async def roles():
            started.add("roles")
            await release.wait()
            return []

        async def inventory():
            started.add("inventory")
            await release.wait()
            return [], [], None

        with (
            patch.object(service, "list_prefixes", side_effect=prefixes),
            patch.object(service, "list_roles", side_effect=roles),
            patch.object(service, "load_ip_inventory", side_effect=inventory),
        ):
            task = asyncio.create_task(service.overview())
            await asyncio.sleep(0)
            self.assertEqual(
                {"prefixes", "roles", "inventory"},
                started,
            )
            release.set()
            result = await task

        self.assertEqual(0, result["summary"]["prefixes"])

    @patch.object(
        IPAMService,
        "load_ip_inventory",
        new_callable=AsyncMock,
        return_value=([], [], None),
    )
    @patch.object(
        IPAMService,
        "list_roles",
        new_callable=AsyncMock,
        return_value=[],
    )
    @patch.object(
        IPAMService,
        "list_prefixes",
        new_callable=AsyncMock,
        return_value=[],
    )
    async def test_overview_cache_avoids_reloading_inventory(
        self,
        list_prefixes,
        list_roles,
        load_inventory,
    ):
        service = IPAMService()

        first = await service.overview()
        second = await service.overview()

        self.assertIs(first, second)
        list_prefixes.assert_awaited_once()
        list_roles.assert_awaited_once()
        load_inventory.assert_awaited_once()


class DeviceTypePerformanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        DeviceTypeService.clear_read_caches()

    @patch.object(
        DeviceTypeService,
        "request",
        new_callable=AsyncMock,
        return_value={
            "results": [{"id": 1, "name": "ZTE"}],
            "next": None,
        },
    )
    async def test_get_all_cache_reuses_catalog_and_returns_copies(self, request):
        service = DeviceTypeService()

        first = await service.get_all(
            "/api/dcim/manufacturers/",
            params={"ordering": "name"},
        )
        first[0]["name"] = "Modificado"
        second = await service.get_all(
            "/api/dcim/manufacturers/",
            params={"ordering": "name"},
        )

        request.assert_awaited_once()
        self.assertEqual("ZTE", second[0]["name"])

    async def test_request_uses_shared_netbox_client(self):
        response = Mock()
        response.is_error = False
        response.json.return_value = {"results": []}
        shared = AsyncMock()
        shared.request.return_value = response

        with patch(
            "app.services.device_type_service.get_shared_netbox_client",
            new=AsyncMock(return_value=shared),
        ) as get_client:
            result = await DeviceTypeService().request(
                "GET",
                "/api/dcim/manufacturers/",
            )

        get_client.assert_awaited_once()
        shared.request.assert_awaited_once()
        self.assertEqual({"results": []}, result)


if __name__ == "__main__":
    unittest.main()
