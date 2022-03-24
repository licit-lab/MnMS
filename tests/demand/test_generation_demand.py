import unittest

from mnms.graph.core import MultiModalGraph
from mnms.mobility_service.car import CarMobilityGraphLayer, PersonalCarMobilityService
from mnms.demand.generation import create_random_demand

class TestGeneration(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

        self.mmgraph = MultiModalGraph()
        self.flow = self.mmgraph.flow_graph

        self.flow.add_node('0', [0, 0])
        self.flow.add_node('1', [1, 0])
        self.flow.add_node('2', [1, 1])
        self.flow.add_node('3', [0, 1])

        self.flow.add_link('0_1', '0', '1')
        self.flow.add_link('1_2', '1', '2')
        self.flow.add_link('2_3', '2', '3')
        self.flow.add_link('3_0', '3', '0')

        self.mmgraph.add_zone('Res', ['0_1', '1_2'])

        serv1 = CarMobilityGraphLayer("s1", 10)
        serv2 = CarMobilityGraphLayer("s2", 9)

        serv1.add_node('S1_0', '0')
        serv1.add_node('S1_1', '1')
        serv1.add_link('SERV1_0_1', 'S1_0', 'S1_1', {'test':0})

        serv2.add_node('S2_1', '1')
        serv2.add_node('S2_2', '2')
        serv2.add_link('SERV2_0_1', 'S2_1', 'S2_2', {'test': 1})

        self.mmgraph.add_layer(serv1)
        self.mmgraph.add_layer(serv2)
        self.mmgraph.connection_layers('S1_S2_1', 'S1_1', 'S2_1', 0, {'time':0})

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_random_demand(self):
        demand = create_random_demand(self.mmgraph)
        self.assertEqual(3, demand.nb_users)
