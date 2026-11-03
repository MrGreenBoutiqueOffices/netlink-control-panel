import unittest

from netlink_panel.cli import bench
from netlink_panel.simulator import SimulatedPanel


class BenchTests(unittest.TestCase):
    def test_real_serial_path_against_pseudo_terminal(self):
        with SimulatedPanel() as panel:
            result = bench(panel.port, duration=1.2)
        self.assertTrue(result["simulated"])
        self.assertGreater(result["heartbeats"], 0)
        self.assertFalse(result["hardware_command_sent"])

    def test_silent_panel_fails_instead_of_reporting_success(self):
        with SimulatedPanel(respond=False) as panel:
            with self.assertRaisesRegex(RuntimeError, "timeout"):
                bench(panel.port, duration=1, timeout=0.2)


if __name__ == "__main__":
    unittest.main()
