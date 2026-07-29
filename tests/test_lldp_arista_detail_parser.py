from __future__ import annotations

import unittest

from app.services.lldp_eos_support import install_lldp_eos_support
from app.services.lldp_discovery_service import LldpDiscoveryService


ARISTA_OUTPUT = '''
Interface Ethernet33 detected 1 LLDP neighbors:

  Neighbor 2899.3a27.77a1/"Ethernet37", age 17 seconds
  - Chassis ID type: MAC address (4)
    Chassis ID     : 2899.3a27.77a1
  - Port ID type: Interface name (5)
    Port ID     : "Ethernet37"
  - Port Description: "*** Po1 TO ARISTA7050MOCA Eth34 ***"
  - System Name: "ARISTA7280SRTNR"
  - System Description: "Arista Networks EOS version 4.23.2F"
  - Management Address Subtype: IPv4
    Management Address        : 172.30.0.35

Interface Ethernet37 detected 1 LLDP neighbors:

  Neighbor 2899.3af4.9062/"Ethernet46", age 12 seconds
  - Chassis ID type: MAC address (4)
    Chassis ID     : 2899.3af4.9062
  - Port ID type: Interface name (5)
    Port ID     : "Ethernet46"
  - System Name: "ARISTA7050SXVEGA"
  - Management Address Subtype: IPv4
    Management Address        : 172.30.0.19
 --More--
Interface Ethernet37 detected 1 LLDP neighbors:

  Neighbor 2899.3af4.9062/"Ethernet46", age 12 seconds
  - Chassis ID type: MAC address (4)
    Chassis ID     : 2899.3af4.9062
  - Port ID type: Interface name (5)
    Port ID     : "Ethernet46"
  - System Name: "ARISTA7050SXVEGA"
  - Management Address Subtype: IPv4
    Management Address        : 172.30.0.19

Interface Ethernet38 detected 1 LLDP neighbors:

  Neighbor 2899.3af4.9062/"Ethernet45", age 12 seconds
  - Chassis ID type: MAC address (4)
    Chassis ID     : 2899.3af4.9062
  - Port ID type: Interface name (5)
    Port ID     : "Ethernet45"
  - System Name: "ARISTA7050SXVEGA"
  - Management Address Subtype: IPv4
    Management Address        : 172.30.0.19
'''


class AristaLldpDetailParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_lldp_eos_support()

    def test_parses_native_eos_interface_blocks_and_removes_duplicates(self):
        observations = LldpDiscoveryService.parse_output(ARISTA_OUTPUT)

        self.assertEqual(3, len(observations))
        first = observations[0]
        self.assertEqual("Ethernet33", first.local_interface)
        self.assertEqual("ARISTA7280SRTNR", first.remote_system_name)
        self.assertEqual("Ethernet37", first.remote_port_id)
        self.assertEqual("172.30.0.35", first.management_ip)
        self.assertEqual("2899.3a27.77a1", first.chassis_id)
        self.assertIn("Po1 TO ARISTA7050MOCA", first.remote_port_description)

        pairs = {
            (item.local_interface, item.remote_system_name, item.remote_port_id)
            for item in observations
        }
        self.assertIn(("Ethernet37", "ARISTA7050SXVEGA", "Ethernet46"), pairs)
        self.assertIn(("Ethernet38", "ARISTA7050SXVEGA", "Ethernet45"), pairs)


if __name__ == "__main__":
    unittest.main()
