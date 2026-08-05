from __future__ import annotations

import os
from pathlib import Path
import re
import unittest
from unittest.mock import AsyncMock, patch

from argon2 import PasswordHasher
from fastapi.testclient import TestClient


os.environ.setdefault("NETBOX_URL", "https://netbox.invalid")
os.environ.setdefault("NETBOX_TOKEN", "test-token")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    PasswordHasher().hash("AdminPassword123"),
)

from app.core.auth import PermissionMiddleware
from app.main import app
from app.routers import documentation as documentation_router
from app.services.change_plan import ChangePlan, ChangeStep
from app.services.ipam_pool_service import (
    IPAMPoolService,
    canonical_network,
    default_pool_form,
    validate_pool_form,
)
from app.services.ipam_service import IPAMService
from app.services.netbox_schema_service import parse_action_schema


SCHEMA = parse_action_schema(
    {
        "actions": {
            "POST": {
                "prefix": {
                    "type": "string",
                    "required": True,
                    "read_only": False,
                },
                "status": {
                    "type": "choice",
                    "required": False,
                    "read_only": False,
                    "choices": [
                        {
                            "value": "active",
                            "display_name": "Activo",
                        },
                        {
                            "value": "reserved",
                            "display_name": "Reservado",
                        },
                    ],
                },
                "vrf": {
                    "type": "field",
                    "required": False,
                    "read_only": False,
                },
                "role": {
                    "type": "field",
                    "required": False,
                    "read_only": False,
                },
                "scope_type": {
                    "type": "string",
                    "required": False,
                    "read_only": False,
                },
                "scope_id": {
                    "type": "integer",
                    "required": False,
                    "read_only": False,
                },
                "is_pool": {
                    "type": "boolean",
                    "required": False,
                    "read_only": False,
                },
                "mark_utilized": {
                    "type": "boolean",
                    "required": False,
                    "read_only": False,
                },
                "description": {
                    "type": "string",
                    "required": False,
                    "read_only": False,
                },
            }
        }
    },
    endpoint="/api/ipam/prefixes/",
    method="POST",
)
FORM_OPTIONS = {
    "schema": SCHEMA,
    "statuses": [
        {"value": "active", "label": "Activo"},
        {"value": "reserved", "label": "Reservado"},
    ],
    "roles": [{"id": 7, "name": "Customer", "display": "Customer"}],
    "vrfs": [{"id": 9, "name": "INTERNET", "display": "INTERNET"}],
    "scopes": [
        {
            "value": "dcim.site:3",
            "label": "Samaná",
            "group": "Site",
        }
    ],
}
FORM_DATA = {
    "prefix": "192.0.2.0/24",
    "status": "active",
    "vrf_id": "9",
    "role_id": "7",
    "scope": "dcim.site:3",
    "description": "Clientes corporativos",
    "change_reason": "Nuevo bloque aprobado para clientes corporativos",
    "parent_id": "",
}
OVERVIEW = {
    "prefixes": [
        {
            "id": 10,
            "prefix": "192.0.2.0/24",
            "_scope_label": "Samaná",
            "_vrf_label": "INTERNET",
            "_role_label": "Customer",
            "_status_label": "Activo",
            "is_pool": True,
        }
    ],
    "pools": [
        {
            "id": 10,
            "prefix": "192.0.2.0/24",
            "_scope_label": "Samaná",
            "_vrf_label": "INTERNET",
            "_role_label": "Customer",
            "_status_label": "Activo",
            "_health": "unknown",
            "_capacity": 256,
            "_used": None,
            "_available": None,
            "_utilization": None,
        }
    ],
    "roles": FORM_OPTIONS["roles"],
    "inventory_warning": None,
    "inventory_ready": False,
    "summary": {
        "prefixes": 1,
        "pools": 1,
        "total_pools": 1,
        "full_pools": 0,
        "critical_pools": 0,
        "available_pools": 0,
        "scopes": 1,
    },
}


def sample_plan() -> ChangePlan:
    return ChangePlan(
        intent="Crear el pool 192.0.2.0/24 en NetBox",
        requested_by="admin",
        steps=(
            ChangeStep(
                step_id="create-ipam-pool",
                action="create",
                resource="ipam.prefix",
                method="POST",
                endpoint="/api/ipam/prefixes/",
                payload={
                    "prefix": "192.0.2.0/24",
                    "status": "active",
                    "is_pool": True,
                    "mark_utilized": False,
                },
                summary="Crear pool 192.0.2.0/24",
                required_permission="devices.create",
                change_reason="Nuevo bloque aprobado",
            ),
        ),
    )


class IPAMPoolValidationTests(unittest.IsolatedAsyncioTestCase):
    def test_cidr_with_host_bits_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "bits de host"):
            canonical_network("192.0.2.10/24")

    def test_form_resolves_explicit_relations(self):
        normalized, errors = validate_pool_form(
            FORM_DATA,
            form_options=FORM_OPTIONS,
        )

        self.assertEqual([], errors)
        self.assertEqual("192.0.2.0/24", normalized["prefix"])
        self.assertEqual(9, normalized["vrf_id"])
        self.assertEqual(7, normalized["role_id"])
        self.assertEqual("dcim.site", normalized["scope_type"])
        self.assertEqual(3, normalized["scope_id"])

    def test_exact_duplicate_is_blocked(self):
        analysis, errors = IPAMPoolService.analyze_candidate(
            network=canonical_network("192.0.2.0/24"),
            prefixes=[
                {
                    "id": 12,
                    "prefix": "192.0.2.0/24",
                    "is_pool": True,
                }
            ],
            parent_id=None,
        )

        self.assertTrue(errors)
        self.assertIn("duplicado", errors[0])
        self.assertIsNone(analysis["parent"])

    def test_parent_and_children_are_exposed_in_preview(self):
        parent = {
            "id": 1,
            "prefix": "192.0.2.0/23",
            "is_pool": False,
        }
        child = {
            "id": 2,
            "prefix": "192.0.2.0/26",
            "is_pool": True,
        }
        analysis, errors = IPAMPoolService.analyze_candidate(
            network=canonical_network("192.0.2.0/24"),
            prefixes=[parent, child],
            parent_id=None,
        )

        self.assertEqual([], errors)
        self.assertEqual(1, analysis["parent"]["id"])
        self.assertEqual([child], analysis["children"])
        self.assertIn("incluye 1 pool", analysis["warnings"][0])

    async def test_plan_uses_options_and_creates_a_pool_payload(self):
        service = IPAMPoolService()
        service.list_prefixes_for_analysis = AsyncMock(return_value=[])

        plan, normalized, analysis, errors = await service.prepare_plan(
            form_data=FORM_DATA,
            requested_by="admin",
            form_options=FORM_OPTIONS,
        )

        self.assertEqual([], errors)
        self.assertIsNotNone(plan)
        payload = plan.steps[0].payload
        self.assertEqual("192.0.2.0/24", payload["prefix"])
        self.assertEqual(9, payload["vrf"])
        self.assertEqual(7, payload["role"])
        self.assertEqual("dcim.site", payload["scope_type"])
        self.assertEqual(3, payload["scope_id"])
        self.assertTrue(payload["is_pool"])
        self.assertFalse(payload["mark_utilized"])
        self.assertIn("admin", payload["changelog_message"])
        self.assertEqual("INTERNET", normalized["vrf_label"])
        self.assertTrue(analysis["warnings"])

    async def test_overlap_inventory_is_scoped_to_the_selected_vrf(self):
        service = IPAMPoolService()
        service._get_all = AsyncMock(return_value=[
            {
                "id": 1,
                "prefix": "192.0.2.0/24",
                "vrf": {"id": 9, "name": "INTERNET"},
            },
            {
                "id": 2,
                "prefix": "192.0.2.0/24",
                "vrf": {"id": 10, "name": "MGMT"},
            },
            {
                "id": 3,
                "prefix": "192.0.2.0/24",
                "vrf": None,
            },
        ])

        prefixes = await service.list_prefixes_for_analysis(
            network=canonical_network("192.0.2.0/24"),
            vrf_id=9,
        )

        self.assertEqual([1], [item["id"] for item in prefixes])


class IPAMReadPerformanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        IPAMService.clear_caches()

    async def test_fast_overview_does_not_wait_for_full_ip_inventory(self):
        service = IPAMService()
        service.list_prefixes = AsyncMock(return_value=[])
        service.list_roles = AsyncMock(return_value=[])
        service.load_ip_inventory = AsyncMock(return_value=([], [], None))

        result = await service.overview(include_inventory=False)

        self.assertFalse(result["inventory_ready"])
        service.load_ip_inventory.assert_not_awaited()
        service.list_prefixes.assert_awaited_once()
        service.list_roles.assert_awaited_once()


class IPAMPoolRouteTests(unittest.TestCase):
    def setUp(self):
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        response = self.client.post(
            "/login",
            data={
                "username": "admin",
                "password": "AdminPassword123",
                "next_url": "/ipam",
            },
            follow_redirects=False,
        )
        self.assertEqual(303, response.status_code)

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    @patch.object(
        IPAMService,
        "overview",
        new_callable=AsyncMock,
        return_value=OVERVIEW,
    )
    def test_ipam_opens_with_deferred_occupancy_and_create_action(
        self,
        overview,
    ):
        response = self.client.get("/ipam")

        self.assertEqual(200, response.status_code)
        self.assertIn('href="/ipam/pools/new"', response.text)
        self.assertIn("calculando la ocupación en segundo plano", response.text)
        self.assertIn(
            "css/ipam.css?v=20260804-status-layout-1",
            response.text,
        )
        self.assertIn(
            "js/ipam.js?v=20260804-status-dom-2",
            response.text,
        )
        self.assertIn("data-ipam-status-title", response.text)
        self.assertIn("data-ipam-status-copy", response.text)
        self.assertFalse(overview.await_args.kwargs["include_inventory"])

    def test_inventory_status_reserves_its_layout_space(self):
        stylesheet = Path("app/static/css/ipam.css").read_text(
            encoding="utf-8",
        )
        status_rule = stylesheet.split(
            ".ipam-inventory-status {",
            maxsplit=1,
        )[1].split("}", maxsplit=1)[0]

        self.assertIn("display: grid;", status_rule)
        self.assertIn(
            "grid-template-columns: 9px minmax(0, 1fr);",
            status_rule,
        )
        self.assertIn(
            ".ipam-inventory-status > div",
            stylesheet,
        )

    def test_inventory_completion_updates_text_not_the_status_dot(self):
        script = Path("app/static/js/ipam.js").read_text(
            encoding="utf-8",
        )

        self.assertIn(
            'status.querySelector("[data-ipam-status-title]")',
            script,
        )
        self.assertIn(
            'status.querySelector("[data-ipam-status-copy]")',
            script,
        )
        self.assertNotIn(
            'status.querySelector("div > span")',
            script,
        )

    @patch.object(
        IPAMService,
        "overview",
        new_callable=AsyncMock,
        return_value={
            **OVERVIEW,
            "inventory_ready": True,
            "pools": [
                {
                    **OVERVIEW["pools"][0],
                    "_health": "critical",
                    "_used": 230,
                    "_available": 26,
                    "_utilization": 89.8,
                }
            ],
        },
    )
    def test_health_filter_loads_inventory_before_filtering(
        self,
        overview,
    ):
        response = self.client.get("/ipam?health=critical")

        self.assertEqual(200, response.status_code)
        self.assertTrue(overview.await_args.kwargs["include_inventory"])

    @patch.object(
        IPAMPoolService,
        "load_form_options",
        new_callable=AsyncMock,
        return_value=FORM_OPTIONS,
    )
    def test_new_pool_form_is_contextual(self, _options):
        response = self.client.get("/ipam/pools/new")

        self.assertEqual(200, response.status_code)
        self.assertIn("Revisar pool", response.text)
        self.assertIn('name="change_reason"', response.text)
        self.assertIn("Duplicado exacto", response.text)
        self.assertIn(
            "css/ipam.css?v=20260804-status-layout-1",
            response.text,
        )

    @patch.object(
        IPAMPoolService,
        "create_pool",
        new_callable=AsyncMock,
        return_value={"id": 77, "prefix": "192.0.2.0/24"},
    )
    @patch.object(
        IPAMPoolService,
        "prepare_plan",
        new_callable=AsyncMock,
    )
    @patch.object(
        IPAMPoolService,
        "load_form_options",
        new_callable=AsyncMock,
        return_value=FORM_OPTIONS,
    )
    def test_preview_is_revalidated_before_the_single_post(
        self,
        _options,
        prepare_plan,
        create_pool,
    ):
        plan = sample_plan()
        normalized = {
            "prefix": "192.0.2.0/24",
            "vrf_label": "INTERNET",
            "scope_label": "Samaná",
            "role_label": "Customer",
            "status_label": "Activo",
        }
        analysis = {"parent": None, "children": [], "warnings": []}
        prepare_plan.return_value = (
            plan,
            normalized,
            analysis,
            [],
        )

        form_response = self.client.get("/ipam/pools/new")
        csrf_match = re.search(
            r'name="csrf" value="([^"]+)"',
            form_response.text,
        )
        self.assertIsNotNone(csrf_match)
        csrf = csrf_match.group(1)

        preview = self.client.post(
            "/ipam/pools/preview",
            data={**FORM_DATA, "csrf": csrf},
        )
        self.assertEqual(200, preview.status_code)
        self.assertIn(plan.confirmation_phrase, preview.text)

        with patch.object(
            documentation_router.settings,
            "netbox_write_enabled",
            True,
        ):
            confirmed = self.client.post(
                "/ipam/pools/confirm",
                data={
                    "csrf": csrf,
                    "plan_id": plan.fingerprint,
                    "confirmation_phrase": plan.confirmation_phrase,
                },
                follow_redirects=False,
            )

        self.assertEqual(303, confirmed.status_code)
        self.assertIn("/ipam?notice=", confirmed.headers["location"])
        self.assertEqual(2, prepare_plan.await_count)
        create_pool.assert_awaited_once()

    def test_pool_routes_require_create_permission(self):
        self.assertEqual(
            "devices.create",
            PermissionMiddleware._required_permission(
                "/ipam/pools/confirm",
                "POST",
            ),
        )
        self.assertEqual(
            "search.view",
            PermissionMiddleware._required_permission(
                "/api/ipam/pools/availability",
                "GET",
            ),
        )


if __name__ == "__main__":
    unittest.main()
