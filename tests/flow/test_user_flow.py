import unittest
from tempfile import TemporaryDirectory

from mnms.flow.user_flow import UserFlow
from mnms.graph.road import RoadDescriptor
from mnms.graph.zone import Zone
from mnms.time import Time, Dt, TimeTable
from mnms.graph.layers import MultiLayerGraph, CarLayer, BusLayer
from mnms.mobility_service.car import PersonalCarMobilityService
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.demand.user import User, Path


class TestUserFlow(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.tempfile = TemporaryDirectory()
        self.pathdir = self.tempfile.name+'/'

        roads = RoadDescriptor()

        roads.register_node('0', [0, 0])
        roads.register_node('1', [0, 40000])
        roads.register_node('2', [1200, 0])
        roads.register_node('3', [1400, 0])
        roads.register_node('4', [3400, 0])

        roads.register_section('0_1', '0', '1')
        roads.register_section('0_2', '0', '2')
        roads.register_section('2_3', '2', '3')
        roads.register_section('3_4', '3', '4')

        roads.register_stop("B2", "2_3", 0)
        roads.register_stop("B3", "3_4", 0)
        roads.register_stop("B4", "3_4", 1)

        roads.add_zone(Zone("res1", {"0_1", "0_2", "2_3"}))
        roads.add_zone(Zone("res2", {"3_4"}))

        car_layer = CarLayer(roads, services=[PersonalCarMobilityService()])
        car_layer.create_node('C0', '0')
        car_layer.create_node('C1', '1')
        car_layer.create_node('C2', '2')

        car_layer.create_link('C0_C1', 'C0', 'C1', costs={'length': 40000}, road_links=['0_1'])
        car_layer.create_link('C0_C2', 'C0', 'C2', costs={'length': 1200}, road_links=['0_2'])

        bus_layer = BusLayer(roads,
                       services=[PublicTransportMobilityService('Bus')])

        bus_layer.create_line("L1",
                        ["B2", "B3", "B4"],
                        [["2_3"], ["3_4"]],
                        TimeTable.create_table_freq('00:00:00', '01:00:00', Dt(minutes=2)))

        mlgraph = MultiLayerGraph([car_layer, bus_layer])

        mlgraph.connect_layers('CAR_BUS', 'C2', 'L1_B2', 0, {'time': 0})

        self.mlgraph = mlgraph
        self.user_flow = UserFlow(1.42)
        self.user_flow.set_graph(mlgraph)
        self.user_flow.set_time(Time('00:01:00'))
        # self.user_flow.initialize()

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.tempfile.cleanup()

    def test_fill(self):
        self.assertTrue(self.mlgraph is self.user_flow._graph)
        self.assertEqual(Time('00:01:00'), self.user_flow._tcurrent)
        self.assertEqual(1.42, self.user_flow._walk_speed)

    def test_request_veh(self):
        user = User('U0', '0', '4', Time('00:01:00'))
        user._current_node = 'C0'
        user.set_path(Path(3400,
                           ['C0', 'C1', 'C2', 'B2', 'B3', 'B4']))
        self.user_flow.step(Dt(minutes=1), [user])

        self.assertIn('U0', self.user_flow.users)
