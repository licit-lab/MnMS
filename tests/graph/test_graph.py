import unittest

from mnms.graph.core import MultiModalGraph
from mnms.mobility_service.car import CarMobilityGraphLayer, PersonalCarMobilityService


class TestCreate(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_create_mmgraph(self):
        MultiModalGraph()

    def test_flow_graph(self):
        mmgraph = MultiModalGraph()
        mmgraph.flow_graph.add_node('0', [0, 0])
        mmgraph.flow_graph.add_node('1', [1, 0])
        mmgraph.flow_graph.add_link('0_1', '0', '1')

        self.assertEqual(mmgraph.flow_graph._adjacency['0'], set('1'))
        self.assertEqual(list(mmgraph.flow_graph.nodes.keys()), ['0', '1'])
        self.assertEqual(list(mmgraph.flow_graph.links.keys()), [('0', '1')])

    def test_mobility_graph(self):
        mmgraph = MultiModalGraph()
        service = CarMobilityGraphLayer('dummy', 10, services=[PersonalCarMobilityService()])

        service.add_node('dummy_0')
        service.add_node('dummy_1')
        service.add_link('0_1', 'dummy_0', 'dummy_1', {'test': 2})

        mmgraph.add_layer(service)

        self.assertEqual(list(mmgraph.mobility_graph.nodes.keys()), ['dummy_0', 'dummy_1'])
        self.assertEqual(list(mmgraph.mobility_graph.links.keys()), [('dummy_0', 'dummy_1')])
