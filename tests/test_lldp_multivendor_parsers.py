from __future__ import annotations

import unittest

from app.services.lldp_discovery_service import LldpDiscoveryService
from app.services.lldp_eos_support import install_lldp_eos_support
from app.services.lldp_vendor_support import install_lldp_vendor_support


CISCO_OUTPUT = """
Local Intf: Gi1/0/1
Chassis id: 0011.2233.4455
Port id: Gi0/1
Port Description: UPLINK
System Name: CISCO-EDGE
System Description: Cisco IOS XE Software
Management Address: 192.0.2.10
"""

NXOS_OUTPUT = """
Local Port id: Ethernet1/1
Chassis id: 00aa.bbcc.ddee
Port id: Ethernet1/49
Port Description: CORE
System Name: NEXUS-CORE
System Description: Cisco NX-OS
Management Address: 192.0.2.20
"""

JUNOS_OUTPUT = """
Local interface        : xe-0/0/0.0
Parent interface       : -
Chassis ID             : 00:11:22:33:44:66
Port ID                : Ethernet49
Port description       : TO-CORE
System name            : QFX-CORE
System description     : Juniper Networks, Inc. qfx
Management address     : 192.0.2.30
"""

MIKROTIK_OUTPUT = """
 0 interface=ether1 address=192.0.2.40 mac-address=00:11:22:33:44:77
   identity="CCR-CORE" interface-name="sfp-sfpplus1"
   system-description="MikroTik RouterOS 7"
"""


class MultivendorLldpParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_lldp_eos_support()
        install_lldp_vendor_support()

    def assert_observation(self, output, local, remote, port, address):
        rows = LldpDiscoveryService.parse_output(output)
        self.assertEqual(1, len(rows))
        self.assertEqual(local, rows[0].local_interface)
        self.assertEqual(remote, rows[0].remote_system_name)
        self.assertEqual(port, rows[0].remote_port_id)
        self.assertEqual(address, rows[0].management_ip)

    def test_cisco_ios_detail(self):
        self.assert_observation(
            CISCO_OUTPUT,
            "Gi1/0/1",
            "CISCO-EDGE",
            "Gi0/1",
            "192.0.2.10",
        )

    def test_cisco_nxos_detail(self):
        self.assert_observation(
            NXOS_OUTPUT,
            "Ethernet1/1",
            "NEXUS-CORE",
            "Ethernet1/49",
            "192.0.2.20",
        )

    def test_juniper_junos_detail(self):
        self.assert_observation(
            JUNOS_OUTPUT,
            "xe-0/0/0.0",
            "QFX-CORE",
            "Ethernet49",
            "192.0.2.30",
        )

    def test_mikrotik_neighbor_detail(self):
        self.assert_observation(
            MIKROTIK_OUTPUT,
            "ether1",
            "CCR-CORE",
            "sfp-sfpplus1",
            "192.0.2.40",
        )


if __name__ == "__main__":
    unittest.main()
