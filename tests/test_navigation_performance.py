from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.services.navigation_read_service import NavigationReadService


class NavigationReadServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        NavigationReadService._cache.clear()
        NavigationReadService._locks.clear()

    async def test_cached_loader_runs_once_and_returns_copies(self):
        loader = AsyncMock(return_value={"items": [1]})

        first = await NavigationReadService._cached(
            "sample",
            60.0,
            loader,
        )
        first["items"].append(2)
        second = await NavigationReadService._cached(
            "sample",
            60.0,
            loader,
        )

        self.assertEqual(1, loader.await_count)
        self.assertEqual({"items": [1]}, second)

    @patch.object(NavigationReadService, "_request", new_callable=AsyncMock)
    async def test_recent_cables_avoids_termination_n_plus_one(self, request):
        request.return_value = {
            "results": [
                {
                    "id": 10,
                    "a_terminations": [
                        {
                            "object_type": "dcim.interface",
                            "object_id": 100,
                            "object": {
                                "device": {"name": "SW-SMN-01"},
                                "name": "Ethernet1",
                            },
                        }
                    ],
                    "b_terminations": [
                        {
                            "object_type": "dcim.interface",
                            "object_id": 101,
                            "object": {
                                "device": {"name": "RTR-SMN-01"},
                                "name": "xe-0/0/0",
                            },
                        }
                    ],
                    "type": {"value": "smf-os2", "label": "SMF OS2"},
                    "status": {"value": "connected", "label": "Connected"},
                    "length": 10,
                    "length_unit": {"value": "m", "label": "m"},
                }
            ]
        }

        cables = await NavigationReadService().list_recent_cables()

        self.assertEqual(1, request.await_count)
        self.assertEqual("SW-SMN-01 · Ethernet1", cables[0]["_a_label"])
        self.assertEqual("RTR-SMN-01 · xe-0/0/0", cables[0]["_b_label"])
        self.assertEqual("Fibra monomodo OS2", cables[0]["_type_label"])
        self.assertEqual("Conectado", cables[0]["_status_label"])
        self.assertEqual("10 m", cables[0]["_length_label"])

    @patch.object(NavigationReadService, "list_recent_cables", new_callable=AsyncMock)
    @patch.object(NavigationReadService, "get_cable_choices", new_callable=AsyncMock)
    @patch.object(NavigationReadService, "list_sites", new_callable=AsyncMock)
    async def test_connection_page_reads_are_concurrent_inputs(
        self,
        list_sites,
        get_choices,
        list_recent,
    ):
        list_sites.return_value = [{"id": 1, "name": "SFM"}]
        get_choices.return_value = {
            "types": [],
            "statuses": [],
            "length_units": [],
        }
        list_recent.return_value = [{"id": 10}]

        result = await NavigationReadService().connection_page_data()

        list_sites.assert_awaited_once()
        get_choices.assert_awaited_once()
        list_recent.assert_awaited_once()
        self.assertEqual(10, result["recent_cables"][0]["id"])


if __name__ == "__main__":
    unittest.main()
