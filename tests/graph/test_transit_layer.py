import unittest
from tempfile import TemporaryDirectory

from mnms.generation.layers import generate_matching_origin_destination_layer
from mnms.graph.layers import CarLayer, BusLayer, MultiLayerGraph
from mnms.graph.road import RoadDescriptor
from mnms.graph.zone import Zone
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.time import TimeTable, Dt
from mnms.io.graph import save_graph, load_graph


class TestIOGraph(unittest.TestCase):
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

        car_layer = CarLayer(self.roads,
                             services=[PersonalMobilityService()])

        car_layer.create_node("C0", "0")
        car_layer.create_node("C1", "1", {"0": {"2"}})
        car_layer.create_node("C2", "2")
        car_layer.create_link("C0_C1", "C0", "C1", {"test": 34.3}, ["0_1"])

        bus_layer = BusLayer(self.roads)

        bus_layer.create_line("L0",
                              ["S0", "S1"],
                              [["0_1", "1_2"]],
                              TimeTable.create_table_freq("08:00:00", "18:00:00", Dt(minutes=10)),
                              True)

        odlayer = generate_matching_origin_destination_layer(self.roads)

        self.mlgraph = MultiLayerGraph([car_layer, bus_layer],
                                       odlayer,
                                       1e-3)

        self.mlgraph.connect_layers("TEST", "C0", "L0_S0", 156, {"test": 1.43})

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_existence(self):
        transit_layer = self.mlgraph.transitlayer

        self.assertEqual(len(transit_layer.links), 3)
        self.assertEqual(len(transit_layer.links["ODLAYER"]), 2)
        self.assertEqual(len(transit_layer.links["BUS"]), 1)
        self.assertEqual(len(transit_layer.links["CAR"]), 2)

    def test_iter(self):
        transit_layer = self.mlgraph.transitlayer
        iterator = list(transit_layer.iter_links())

        self.assertEqual(len(iterator), 11)

    def test_iter_inter(self):
        transit_layer = self.mlgraph.transitlayer
        iterator = list(transit_layer.iter_inter_links())

        self.assertEqual(len(iterator), 1)

        link = self.mlgraph.graph.links[iterator[0]]

        self.assertDictEqual(link.costs, {"test": 1.43})
        self.assertEqual(link.length, 156)
