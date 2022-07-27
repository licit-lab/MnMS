import unittest

from mnms.graph.zone import MultiModalGraph
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
        mmgraph.flow_graph.create_node('0', [0, 0])
        mmgraph.flow_graph.create_node('1', [1, 0])
        mmgraph.flow_graph.create_link('0_1', '0', '1')

        self.assertEqual(mmgraph.flow_graph.nodes['0'].adj, set('1'))
        self.assertEqual(list(mmgraph.flow_graph.nodes.keys()), ['0', '1'])
        self.assertEqual(list(mmgraph.flow_graph.sections.keys()), [('0', '1')])

    def test_mobility_graph(self):
        mmgraph = MultiModalGraph()
        service = CarMobilityGraphLayer('dummy', 10, services=[PersonalCarMobilityService()])

        service.create_node('dummy_0', None)
        service.create_node('dummy_1', None)
        service.create_link('0_1', 'dummy_0', 'dummy_1', [], {'test': 2})

        mmgraph.add_layer(service)

        self.assertEqual(list(mmgraph.mobility_graph.nodes.keys()), ['dummy_0', 'dummy_1'])
        self.assertEqual(list(mmgraph.mobility_graph.sections.keys()), [('dummy_0', 'dummy_1')])

    def test_exclude_movements(self):
        service = CarMobilityGraphLayer('dummy', 10, services=[PersonalCarMobilityService()])

        service.create_node('A', None)
        service.create_node('B', None, {'A': {'D'}})
        service.create_node('C', None)
        service.create_node('D', None)
        service.create_node('E', None)

        service.create_link('A_B', 'A', 'B', [], {})
        service.create_link('B_D', 'B', 'D', [], {})
        service.create_link('B_C', 'B', 'C', [], {})
        service.create_link('B_E', 'B', 'E', [], {})

        self.assertEqual({'D', 'C', 'E'}, service.graph.nodes['B'].adj)
        self.assertEqual({'C', 'E'}, set(service.graph.nodes['B'].get_exits('A')))
