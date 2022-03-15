import unittest

from mnms.graph.core import MultiModalGraph
from mnms.mobility_service.personal_car import PersonalCar
from mnms.mobility_service.public_transport import PublicTransport
from mnms.tools.time import TimeTable, Dt
from mnms.vehicles.veh_type import Bus


class TestHub(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

        mmgraph = MultiModalGraph()

        flow_graph = mmgraph.flow_graph

        flow_graph.add_node('0', [0, 0])
        flow_graph.add_node('1', [1, 0])
        flow_graph.add_node('2', [2, 0])
        flow_graph.add_node('3', [3, 0])

        flow_graph.add_node('4', [0.5, 0.5])
        flow_graph.add_node('5', [1, 1])
        flow_graph.add_node('6', [1.5, 2])
        flow_graph.add_node('7', [3, 2])

        flow_graph.add_node('8', [0, 1])
        flow_graph.add_node('9', [2, 1])
        flow_graph.add_node('10', [3, 1])

        flow_graph.add_link('0_1', '0', '1')
        flow_graph.add_link('1_2', '1', '2')
        flow_graph.add_link('2_3', '2', '3')
        flow_graph.add_link('1_5', '1', '5')
        flow_graph.add_link('4_5', '4', '5')
        flow_graph.add_link('8_5', '8', '5')
        flow_graph.add_link('5_9', '5', '9')
        flow_graph.add_link('9_10', '9', '10')
        flow_graph.add_link('5_6', '5', '6')
        flow_graph.add_link('6_7', '6', '7')
        flow_graph.add_link('10_7', '10', '7')
        flow_graph.add_link('3_10', '3', '10')

        tram = PersonalCar('TRAM', 10)
        tram.add_node('0', '0')
        tram.add_node('1', '1')
        tram.add_node('5', '5')

        tram.add_link('0_1', '0', '1', {'time': 1}, ['0_1'], [0])
        tram.add_link('1_5', '1', '5', {'time': 1}, ['1_5'], [0])

        bus = PublicTransport('BUS', Bus, 8.3)

        l0 = bus.add_line('L0', TimeTable.create_table_freq("07:00:00", "18:00:00", Dt(minutes=15)))
        l0.add_stop('8', '8')
        l0.add_stop('5', '5')
        l0.add_stop('9', '9')
        l0.add_stop('10', '10')
        l0.add_stop('7', '7')

        l0.connect_stops('8_5', '8', '5', 100, reference_links='8_5', reference_lane_ids=[0])
        l0.connect_stops('5_9', '5', '9', 100, reference_links='5_9', reference_lane_ids=[0])
        l0.connect_stops('9_10', '9', '10', 100, reference_links='9_10', reference_lane_ids=[0])
        l0.connect_stops('10_7', '10', '7', 100, reference_links='10_7', reference_lane_ids=[0])

        l1 = bus.add_line('L1', TimeTable.create_table_freq("07:00:00", "18:00:00", Dt(minutes=15)))
        l1.add_stop('4', '4')
        l1.add_stop('5', '5')
        l1.add_stop('6', '6')
        l1.add_stop('7', '7')

        l1.connect_stops('4_5', '4', '5', 1000, reference_links='4_5', reference_lane_ids=[0])
        l1.connect_stops('5_6', '5', '6', 1000, reference_links='5_6', reference_lane_ids=[0])
        l1.connect_stops('6_7', '6', '7', 1000, reference_links='6_7', reference_lane_ids=[0])

        bus.connect_lines('L0', 'L1', '5')
        bus.connect_lines('L0', 'L1', '7')

        mmgraph.add_mobility_service(tram)
        mmgraph.add_mobility_service(bus)

        self.mmgraph = mmgraph

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_construct_hub_exclusion(self):
        self.mmgraph.construct_hub('1', 0.75, exclusion_matrix={'BUS': {'TRAM'}})
        self.assertIn(('1', 'L1_4'), self.mmgraph.mobility_graph.links)

    def test_construct_hub(self):
        self.mmgraph.construct_hub('1', 0.75)
        self.assertIn(('1', 'L1_4'), self.mmgraph.mobility_graph.links)
        self.assertIn(('L1_4', '1'), self.mmgraph.mobility_graph.links)
