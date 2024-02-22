import tempfile
from pathlib import Path
import unittest

from mnms.generation.layers import generate_matching_origin_destination_layer
from mnms.graph.layers import CarLayer, BusLayer, MultiLayerGraph
from mnms.graph.road import RoadDescriptor
from mnms.graph.zone import Zone
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.time import TimeTable, Dt
from mnms.io.graph import save_graph, load_graph


class TestTransitLayer(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.temp_dir_results = tempfile.TemporaryDirectory()
        self.dir_results = Path(self.temp_dir_results.name)

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()

    def init_test(self, sc):
        """Method to initiate the different tests of this class.
        """
        if sc in ['1', '2', '3']:
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
            car_layer.create_node("C1", "1")
            car_layer.create_node("C2", "2")
            car_layer.create_link("C0_C1", "C0", "C1", {"PersonalVehicle": {"test": 34.3}}, ["0_1"])

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
        if sc in ['2']:
            self.mlgraph.connect_layers("TEST_", "C0", "L0_S0", 156, {"test": 0})
        if sc in ['3']:
            self.mlgraph.connect_origindestination_layers(1e-1)

    def test_existence(self):
        self.init_test('1')
        transit_layer = self.mlgraph.transitlayer

        self.assertEqual(len(transit_layer.links), 3)
        self.assertEqual(len(transit_layer.links["ODLAYER"]["CAR"]), 3)
        self.assertEqual(len(transit_layer.links["ODLAYER"]["BUS"]), 2)
        self.assertEqual(len(transit_layer.links["BUS"]["ODLAYER"]), 2)
        self.assertEqual(len(transit_layer.links["BUS"]["CAR"]), 0)
        self.assertEqual(len(transit_layer.links["CAR"]["ODLAYER"]), 3)
        self.assertEqual(len(transit_layer.links["CAR"]["BUS"]), 1)

    def test_iter(self):
        self.init_test('1')
        transit_layer = self.mlgraph.transitlayer
        iterator = list(transit_layer.iter_links())

        self.assertEqual(len(iterator), 11)

    def test_iter_inter(self):
        self.init_test('1')
        transit_layer = self.mlgraph.transitlayer
        iterator = list(transit_layer.iter_inter_links())

        self.assertEqual(len(iterator), 1)

        link = self.mlgraph.graph.links[iterator[0]]

        self.assertDictEqual(link.costs["WALK"], {"test": 1.43})
        self.assertEqual(link.length, 156)

    def test_double_transit_link_connect_layers(self):
        """Check that we cannot create two times the same transit links.
        """
        self.init_test('2')
        transit_layer = self.mlgraph.transitlayer
        self.assertEqual(len(transit_layer.links["CAR"]["BUS"]), 1)
        self.assertEqual(transit_layer.links["CAR"]["BUS"], ['TEST'])
        self.assertEqual(self.mlgraph.graph.nodes["C0"].adj["L0_S0"].costs, {'WALK': {'test': 1.43}})

    def test_double_transit_link_connect_origindestination_layers(self):
        """Check that we cannot create two times the same transit links.
        """
        self.init_test('3')
        transit_layer = self.mlgraph.transitlayer
        self.assertEqual(len(transit_layer.links), 3)
        print(transit_layer.links["ODLAYER"]["CAR"])
        self.assertEqual(len(transit_layer.links["ODLAYER"]["CAR"]), 3)
        self.assertEqual(len(transit_layer.links["ODLAYER"]["BUS"]), 2)
        self.assertEqual(len(transit_layer.links["BUS"]["ODLAYER"]), 2)
        self.assertEqual(len(transit_layer.links["CAR"]["ODLAYER"]), 3)
