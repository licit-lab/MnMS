import unittest
from dataclasses import asdict

from mnms.graph.road import RoadDescriptor
from mnms.graph.zone import Zone


class TestLayers(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

        self.roads = RoadDescriptor()
        self.roads.register_node("0", [0, 0])
        self.roads.register_node("1", [1, 0])
        self.roads.register_node("2", [2, 0])

        self.roads.register_section("0_1", "0", "1", 1)
        self.roads.register_section("1_2", "1", "2", 1)

        self.roads.register_stop("S0", "0_1", 0.4)
        self.roads.register_stop("S1", "1_2", 0.9)

        self.roads.add_zone(Zone("Z0", {"0_1"}, []))
        self.roads.add_zone(Zone("Z1", {"1_2"}, []))

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_fill(self):
        self.assertIn("0", self.roads.nodes)
        self.assertIn("1", self.roads.nodes)
        self.assertIn("2", self.roads.nodes)

        self.assertListEqual([0, 0], self.roads.nodes["0"].position.tolist())
        self.assertListEqual([1, 0], self.roads.nodes["1"].position.tolist())
        self.assertListEqual([2, 0], self.roads.nodes["2"].position.tolist())

        self.assertIn("0_1", self.roads.sections)
        self.assertIn("1_2", self.roads.sections)

        self.assertEqual("Z0", self.roads.sections["0_1"].zone)
        self.assertEqual("Z1", self.roads.sections["1_2"].zone)

        self.assertIn("S0", self.roads.stops)
        self.assertIn("S1", self.roads.stops)

        self.assertAlmostEqual([0.4, 0], self.roads.stops["S0"].absolute_position.tolist())
        self.assertAlmostEqual([1.9, 0], self.roads.stops["S1"].absolute_position.tolist())

    def test_serialization(self):
        data_dict = self.roads.__dump__()
        new_roads = RoadDescriptor.__load__(data_dict)

        self.assertListEqual(list(data_dict["NODES"].keys()), list(new_roads.nodes.keys()))
        self.assertListEqual(list(data_dict["SECTIONS"].keys()), list(new_roads.sections.keys()))
        self.assertListEqual(list(data_dict["STOPS"].keys()), list(new_roads.stops.keys()))
        self.assertListEqual(list(data_dict["ZONES"].keys()), list(new_roads.zones.keys()))
