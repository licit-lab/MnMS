import json
import unittest
from tempfile import TemporaryDirectory

from mnms.generation.layers import generate_matching_origin_destination_layer
from mnms.graph.layers import CarLayer, BusLayer, MultiLayerGraph
from mnms.graph.road import RoadDescriptor
from mnms.graph.zone import Zone
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.time import TimeTable, Dt
from mnms.io.graph import save_graph, load_graph, save_transit_links, save_transit_link_odlayer


class TestIOGraphTransit(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

        self.tempdir = TemporaryDirectory()

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

    def tearDown(self):
        """Concludes and closes the test.
        """
        try:
            self.tempdir.cleanup()
        except:
            pass

    def test_read_write_all(self):
        save_transit_links(self.mlgraph, self.tempdir.name+"/all_transit.json")
        with open(self.tempdir.name+"/all_transit.json", "r") as f:
            data = json.load(f)

        for link in data['LINKS']:
            link_id = link['ID']
            assert link_id in self.mlgraph.graph.links

    def test_read_write_odlayer_links(self):
        save_transit_link_odlayer(self.mlgraph.odlayer, self.tempdir.name+"/odlayer_transit.json")
        with open(self.tempdir.name+"/odlayer_transit.json", "r") as f:
            data = json.load(f)

        data = set(l["ID"] for l in data["LINKS"])

        for origin in self.mlgraph.odlayer.origins.values():
            for link in origin.adj:
                assert link.id in data
        for destination in self.mlgraph.odlayer.destinations.values():
            for link in destination.radj:
                assert link.id in data