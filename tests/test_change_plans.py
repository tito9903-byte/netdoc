from __future__ import annotations

import unittest

from app.services.cable_planner import (
    CableEndpoint,
    build_cable_plan,
    endpoint_from_netbox,
)
from app.services.change_plan import (
    ChangePlan,
    ChangePlanError,
    ChangeStep,
    redact_sensitive,
    require_confirmation,
)
from app.services.netbox_capabilities import (
    capability_for,
    validate_plan_capabilities,
)


class ChangePlanTests(unittest.TestCase):
    def test_delete_operations_are_rejected(self):
        with self.assertRaises(ChangePlanError):
            ChangeStep(
                step_id="delete-device",
                action="DEVICE_DELETE",
                resource="device",
                method="DELETE",
                endpoint="/api/dcim/devices/1/",
                payload={},
                summary="Eliminar equipo.",
                required_permission="devices.create",
                change_reason="Prueba.",
            )

    def test_sensitive_values_are_redacted_recursively(self):
        payload = {
            "name": "OLT-01",
            "token": "abc",
            "nested": {
                "session_secret": "hidden",
                "description": "visible",
            },
        }
        public = redact_sensitive(payload)
        self.assertEqual(public["token"], "[REDACTADO]")
        self.assertEqual(public["nested"]["session_secret"], "[REDACTADO]")
        self.assertEqual(public["nested"]["description"], "visible")

    def test_confirmation_is_bound_to_plan_fingerprint(self):
        plan = build_cable_plan(
            requested_by="admin",
            endpoint_a=CableEndpoint("dcim.interface", 1, "SW1 · Ethernet1"),
            endpoint_b=CableEndpoint("dcim.interface", 2, "SW2 · Ethernet1"),
            cable_type="smf-os2",
        )
        require_confirmation(plan, plan.confirmation_phrase)
        with self.assertRaises(ChangePlanError):
            require_confirmation(plan, "CONFIRMAR OTROPLAN")

    def test_plan_dependencies_must_reference_previous_steps(self):
        step = ChangeStep(
            step_id="second",
            action="DEVICE_CREATE",
            resource="device",
            method="POST",
            endpoint="/api/dcim/devices/",
            payload={"name": "OLT-01"},
            summary="Crear OLT.",
            required_permission="devices.create",
            change_reason="Alta física.",
            depends_on=("first",),
        )
        with self.assertRaises(ChangePlanError):
            ChangePlan(
                intent="Crear equipo.",
                requested_by="admin",
                steps=(step,),
            )

    def test_unknown_endpoint_is_not_in_allowlist(self):
        self.assertIsNone(capability_for("POST", "/api/users/users/"))


class CablePlannerTests(unittest.TestCase):
    def test_builds_netbox_cable_payload(self):
        plan = build_cable_plan(
            requested_by="luis",
            endpoint_a=CableEndpoint("dcim.interface", 10, "OLT-01 · uplink-1"),
            endpoint_b=CableEndpoint("dcim.interface", 20, "CORE-01 · Ethernet5"),
            status="connected",
            cable_type="smf-os2",
            label="FO-SMN-001",
            color="#00c8d2",
            length="125.5",
            length_unit="m",
            description="Enlace principal.",
            source="ai",
        )

        self.assertTrue(plan.executable)
        self.assertEqual(len(plan.steps), 1)
        step = plan.steps[0]
        self.assertEqual(step.endpoint, "/api/dcim/cables/")
        self.assertEqual(step.payload["a_terminations"][0]["object_id"], 10)
        self.assertEqual(step.payload["b_terminations"][0]["object_id"], 20)
        self.assertEqual(step.payload["color"], "00c8d2")
        self.assertEqual(step.payload["length"], "125.5")
        self.assertIn("changelog_message", step.payload)
        self.assertEqual(
            validate_plan_capabilities(plan.steps, for_ai=True)[0].key,
            "dcim.cable.create",
        )

    def test_rejects_same_endpoint(self):
        endpoint = CableEndpoint("dcim.interface", 10, "SW1 · Ethernet1")
        with self.assertRaises(ChangePlanError):
            build_cable_plan(
                requested_by="admin",
                endpoint_a=endpoint,
                endpoint_b=endpoint,
            )

    def test_rejects_connected_endpoint(self):
        with self.assertRaises(ChangePlanError):
            build_cable_plan(
                requested_by="admin",
                endpoint_a=CableEndpoint(
                    "dcim.interface",
                    10,
                    "SW1 · Ethernet1",
                    cable_id=99,
                ),
                endpoint_b=CableEndpoint(
                    "dcim.interface",
                    20,
                    "SW2 · Ethernet1",
                ),
            )

    def test_rejects_invalid_color_and_negative_length(self):
        endpoints = {
            "endpoint_a": CableEndpoint("dcim.interface", 1, "A"),
            "endpoint_b": CableEndpoint("dcim.interface", 2, "B"),
        }
        with self.assertRaises(ChangePlanError):
            build_cable_plan(
                requested_by="admin",
                color="blue",
                **endpoints,
            )
        with self.assertRaises(ChangePlanError):
            build_cable_plan(
                requested_by="admin",
                length=-1,
                **endpoints,
            )

    def test_endpoint_is_resolved_from_netbox_payload(self):
        endpoint = endpoint_from_netbox({
            "id": 44,
            "name": "Ethernet1",
            "device": {"name": "CORE-01"},
            "enabled": True,
            "cable": None,
            "connected_endpoints": [],
        })
        self.assertEqual(endpoint.display, "CORE-01 · Ethernet1")
        self.assertFalse(endpoint.connected)
        self.assertTrue(endpoint.enabled)


if __name__ == "__main__":
    unittest.main()
