import unittest
from tempfile import TemporaryDirectory

from mnms.demand import User
from mnms.flow.MFD import MFDFlow, Reservoir
from mnms.graph.shortest_path import Path
from mnms.time import Dt, TimeTable, Time
from mnms.graph.layers import MultiLayerGraph
from mnms.graph.road import RoadDescription
from mnms.mobility_service.car import CarMobilityGraphLayer, PersonalCarMobilityService
from mnms.mobility_service.public_transport import PublicTransportMobilityService, BusMobilityGraphLayer
from mnms.vehicles.veh_type import Vehicle


class TestMFDFlow(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.tempfile = TemporaryDirectory()
        self.pathdir = self.tempfile.name+'/'

        mmgraph = MultiLayerGraph()
        roads = RoadDescription()


        roads.create_node('0', [0, 0])
        roads.create_node('1', [0, 40000])
        roads.create_node('2', [1200, 0])
        roads.create_node('3', [1400, 0])
        roads.create_node('4', [3400, 0])

        flow_graph.create_link('0_1', '0', '1')
        flow_graph.create_link('0_2', '0', '2')
        flow_graph.create_link('2_3', '2', '3')
        flow_graph.create_link('3_4', '3', '4')

        mmgraph.add_zone('res1', ['0_1', '0_2', '2_3'])
        mmgraph.add_zone('res2', ['3_4'])

        self.personal_car = PersonalCarMobilityService()
        car = CarMobilityGraphLayer('car_layer', 10,
                                    services=[self.personal_car])
        car.create_node('C0', '0')
        car.create_node('C1', '1')
        car.create_node('C2', '2')

        car.create_link('C0_C1', 'C0', 'C1', costs={'length':40000}, reference_links=['0_1'])
        car.create_link('C0_C2', 'C0', 'C2', costs={'length':1200}, reference_links=['0_2'])

        self.public_transport = PublicTransportMobilityService('Bus')
        bus = BusMobilityGraphLayer('BusLayer', 10,
                                    services=[self.public_transport])

        bus_line = bus.add_line('L1', TimeTable.create_table_freq('00:00:00', '01:00:00', Dt(minutes=2)))

        bus_line.add_stop('B2', '2')
        bus_line.add_stop('B3', '3')
        bus_line.add_stop('B4', '4')

        bus_line.connect_stops('B2_B3', 'B2', 'B3', 200, reference_links=['2_3'])
        bus_line.connect_stops('B3_B4', 'B3', 'B4', 2000, reference_links=['3_4'])

        mmgraph.add_layer(car)
        mmgraph.add_layer(bus)

        mmgraph.connect_layers('CAR_BUS', 'C2', 'B2', 100, {'time':0})

        self.mmgraph = mmgraph

        self.flow = MFDFlow()
        self.flow.set_graph(mmgraph)

        res1 = Reservoir.fromZone(mmgraph, 'res1', lambda x: {k: 42 for k in x})
        res2 = Reservoir.fromZone(mmgraph, 'res2', lambda x: {k: 0.23 for k in x})

        self.flow.add_reservoir(res1)
        self.flow.add_reservoir(res2)
        self.flow.set_time(Time('09:00:00'))

        self.flow.initialize()

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.tempfile.cleanup()
        self.flow.veh_manager.empty()
        Vehicle._counter = 0

    def test_fill(self):
        self.assertIn('res1', self.flow.dict_speeds)
        self.assertIn('res2', self.flow.dict_speeds)
        self.assertIn(None, self.flow.dict_speeds)
        self.assertEqual('09:00:00.00', self.flow.time)

    def test_accumulation_speed(self):
        user = User('U0', '0', '4', Time('00:01:00'))
        user.set_path(Path(3400,
                           ['C0', 'C2', 'B2', 'B3', 'B4']))
        self.personal_car.request_vehicle(user, 'C2')
        self.flow.step(Dt(seconds=1))
        self.assertDictEqual({'CAR': 1, 'BUS': 0}, self.flow.dict_accumulations['res1'])
        self.assertDictEqual({'BUS': 42, 'CAR': 42}, self.flow.dict_speeds['res1'])
        self.assertAlmostEqual(1158.0, self.personal_car.fleet.vehicles['0']._remaining_link_length)