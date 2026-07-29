from __future__ import annotations

from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from starlette.datastructures import FormData

from app.main import app
from app.services.component_sequence_service import ComponentSequenceService
from app.services.device_interface_sync_service import DeviceInterfaceSyncService
from app.services.device_type_service import DeviceTypeServiceError


ROOT = Path(__file__).resolve().parents[1]


class ComponentSequenceServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_creates_two_gpon_sequences_in_one_bulk_payload(self):
        request = AsyncMock(
            return_value=[{"id": number} for number in range(1, 9)]
        )
        service = object.__new__(ComponentSequenceService)
        service.client = SimpleNamespace(request=request)
        service.component_fields = AsyncMock(
            return_value=[
                {
                    "name": "type",
                    "label": "Tipo",
                    "required": True,
                    "input_type": "select",
                    "choices": [{"value": "gpon", "label": "GPON"}],
                    "multiple": False,
                }
            ]
        )
        form = FormData([
            ("sequence_pattern", "gpon-olt_1/2/{n}"),
            ("sequence_start", "1"),
            ("sequence_count", "4"),
            ("sequence_pattern", "gpon-olt_1/3/{n}"),
            ("sequence_start", "1"),
            ("sequence_count", "4"),
            ("type", "gpon"),
        ])

        created = await service.create_components(
            "interface",
            device_type_id=55,
            form=form,
        )

        self.assertEqual(8, len(created))
        request.assert_awaited_once()
        self.assertEqual(
            "/api/dcim/interface-templates/",
            request.await_args.args[1],
        )
        payload = request.await_args.kwargs["json_body"]
        self.assertEqual(
            [
                "gpon-olt_1/2/1",
                "gpon-olt_1/2/2",
                "gpon-olt_1/2/3",
                "gpon-olt_1/2/4",
                "gpon-olt_1/3/1",
                "gpon-olt_1/3/2",
                "gpon-olt_1/3/3",
                "gpon-olt_1/3/4",
            ],
            [item["name"] for item in payload],
        )
        self.assertTrue(all(item["device_type"] == 55 for item in payload))
        self.assertTrue(all(item["type"] == "gpon" for item in payload))

    async def test_rejects_duplicate_names_between_sequences(self):
        service = object.__new__(ComponentSequenceService)
        form = FormData([
            ("sequence_pattern", "Gi0/{n}"),
            ("sequence_start", "1"),
            ("sequence_count", "2"),
            ("sequence_pattern", "Gi0/{n}"),
            ("sequence_start", "2"),
            ("sequence_count", "2"),
        ])

        with self.assertRaises(DeviceTypeServiceError) as raised:
            service._build_sequence_names(form)

        self.assertIn("duplicados", raised.exception.message)


class DeviceInterfaceSyncServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_creates_only_missing_interfaces_and_preserves_existing(self):
        request = AsyncMock()

        async def request_side_effect(method, endpoint, **kwargs):
            if method == "GET" and endpoint == "/api/dcim/devices/214/":
                return {
                    "id": 214,
                    "name": "SWI-01",
                    "device_type": {"id": 501, "display": "S3900-24F4S-R"},
                }
            if method == "POST" and endpoint == "/api/dcim/interfaces/":
                return [{"id": 900, **kwargs["json_body"][0]}]
            self.fail(f"Solicitud inesperada: {method} {endpoint}")

        request.side_effect = request_side_effect

        async def get_all_side_effect(endpoint, params=None, **_kwargs):
            if endpoint == "/api/dcim/interface-templates/":
                return [
                    {"id": 1, "name": "g0/1", "type": {"value": "1000base-x-sfp", "label": "SFP"}},
                    {"id": 2, "name": "g0/2", "type": {"value": "1000base-x-sfp", "label": "SFP"}, "enabled": True},
                    {"id": 3, "name": "MGMT", "type": {"value": "1000base-t", "label": "1GBASE-T"}},
                ]
            if endpoint == "/api/dcim/interfaces/":
                return [
                    {"id": 10, "name": "g0/1", "type": {"value": "1000base-x-sfp", "label": "SFP"}},
                    {"id": 11, "name": "MGMT", "type": {"value": "virtual", "label": "Virtual"}},
                ]
            self.fail(f"Listado inesperado: {endpoint}")

        service = object.__new__(DeviceInterfaceSyncService)
        service.client = SimpleNamespace(
            request=request,
            get_all=AsyncMock(side_effect=get_all_side_effect),
        )

        result = await service.synchronize(214)

        self.assertEqual(1, result["created_count"])
        self.assertEqual(1, result["matching_count"])
        self.assertEqual(1, result["conflict_count"])
        post_call = request.await_args_list[-1]
        payload = post_call.kwargs["json_body"]
        self.assertEqual(1, len(payload))
        self.assertEqual("g0/2", payload[0]["name"])
        self.assertEqual(214, payload[0]["device"])
        self.assertEqual("1000base-x-sfp", payload[0]["type"])


class InterfaceSyncRouteTests(unittest.TestCase):
    @staticmethod
    def login(client: TestClient) -> None:
        response = client.post(
            "/login",
            data={
                "username": "admin",
                "password": "AdminPassword123",
                "next_url": "/devices/214",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    @staticmethod
    def preview() -> dict:
        return {
            "device": {"id": 214, "name": "SWI-01"},
            "device_type": {"id": 501, "display": "S3900-24F4S-R"},
            "template_count": 3,
            "existing_count": 1,
            "missing_count": 2,
            "matching_count": 1,
            "conflict_count": 0,
            "missing": [
                {"name": "g0/2", "_type_label": "SFP"},
                {"name": "g0/3", "_type_label": "SFP"},
            ],
            "conflicts": [],
        }

    @patch(
        "app.routers.model_builder.DeviceInterfaceSyncService.preview",
        new_callable=AsyncMock,
    )
    @patch(
        "app.routers.model_builder.DeviceInterfaceSyncService.synchronize",
        new_callable=AsyncMock,
    )
    def test_sync_modal_and_post_redirect(
        self,
        synchronize,
        preview,
    ):
        preview.return_value = self.preview()
        synchronize.return_value = {
            **self.preview(),
            "created_count": 2,
        }

        # La suite aislada usa escritura deshabilitada por seguridad. Esta prueba
        # activa explícitamente el interruptor solo dentro de su propio contexto,
        # porque valida el flujo POST exitoso sin realizar llamadas reales a NetBox.
        with patch(
            "app.routers.model_builder.settings.netbox_write_enabled",
            True,
        ), TestClient(app) as client:
            self.login(client)
            response = client.get("/devices/214/interfaces/sync?modal=1")
            self.assertEqual(200, response.status_code)
            self.assertIn("Crear 2 interfaces faltantes", response.text)
            match = re.search(
                r'name="csrf_token" value="([^"]+)"',
                response.text,
            )
            self.assertIsNotNone(match)

            post = client.post(
                "/devices/214/interfaces/sync",
                data={"csrf_token": match.group(1)},
                follow_redirects=False,
            )

        self.assertEqual(303, post.status_code)
        self.assertIn("interfaces_synced=2", post.headers["location"])
        self.assertIn("#interfaces", post.headers["location"])


class InterfaceSyncPresentationTests(unittest.TestCase):
    def test_device_detail_and_component_form_expose_new_actions(self):
        device_template = (
            ROOT / "app/templates/device_detail.html"
        ).read_text(encoding="utf-8")
        component_template = (
            ROOT / "app/templates/device_type_component_new.html"
        ).read_text(encoding="utf-8")
        javascript = (
            ROOT / "app/static/js/component_sequences.js"
        ).read_text(encoding="utf-8")

        self.assertIn("Sincronizar desde modelo", device_template)
        self.assertIn("/interfaces/sync", device_template)
        self.assertIn("data-add-sequence", component_template)
        self.assertIn('name="sequence_pattern"', component_template)
        self.assertIn("Agregar otra secuencia", component_template)
        self.assertIn("maximumComponents = 256", javascript)


if __name__ == "__main__":
    unittest.main()
