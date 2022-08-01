import unittest

from mnms.graph.road import RoadDescription


class TestLayers(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

        self.roads = RoadDescription()
        self.roads.register_node("0", [0, 0])
        self.roads.register_node("1", [1, 0])
        self.roads.register_node("2", [2, 0])

        self.roads.register_section("0_1", "0", "1", 1, zone="Z0")
        self.roads.register_section("1_2", "1", "2", 1, zone="Z1")

        self.roads.register_stop("S0", "0_1", 0.4)
        self.roads.register_stop("S1", "1_2", 0.9)

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_fill(self):
        self.assertIn("0", self.roads.nodes)
        self.assertIn("1", self.roads.nodes)
        self.assertIn("2", self.roads.nodes)

        self.assertListEqual([0, 0], self.roads.nodes["0"].tolist())
        self.assertListEqual([1, 0], self.roads.nodes["1"].tolist())
        self.assertListEqual([2, 0], self.roads.nodes["2"].tolist())

        self.assertIn("0_1", self.roads.sections)
        self.assertIn("1_2", self.roads.sections)

        self.assertEqual("Z0", self.roads.sections["0_1"]['zone'])
        self.assertEqual("Z1", self.roads.sections["1_2"]['zone'])

        self.assertIn("S0", self.roads.stops)
        self.assertIn("S1", self.roads.stops)

        self.assertAlmostEqual([0.4, 0], self.roads.stops["S0"]["absolute_position"].tolist())
        self.assertAlmostEqual([1.9, 0], self.roads.stops["S1"]["absolute_position"].tolist())

    def test_serialization(self):
        data_dict = self.roads.__dump__()
        new_roads = RoadDescription.__load__(data_dict)

        self.assertDictEqual(data_dict["NODES"], new_roads.nodes)
        self.assertDictEqual(data_dict["SECTIONS"], new_roads.sections)
        self.assertDictEqual(data_dict["STOPS"], new_roads.stops)