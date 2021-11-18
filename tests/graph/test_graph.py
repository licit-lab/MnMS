import unittest

from routeservice.graph.structure import MultiModalGraph

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
        service = mmgraph.add_mobility_service('dummy')

        service.add_node('0')
        service.add_node('1')
        service.add_link('0_1', '0', '1', {'test': 2})

        self.assertEqual(list(mmgraph.mobility_graph.nodes.keys()), ['dummy_0', 'dummy_1'])
        self.assertEqual(list(mmgraph.mobility_graph.links.keys()), [('dummy_0', 'dummy_1')])


class TestExtract(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

        self.mmgraph = MultiModalGraph()
        self.flow = self.mmgraph.flow_graph
        self.mobility = self.mmgraph.mobility_graph

        self.flow.add_node('0', [0, 0])
        self.flow.add_node('1', [1, 0])
        self.flow.add_node('2', [1, 1])
        self.flow.add_node('3', [0, 1])

        self.flow.add_link('0_1', '0', '1')
        self.flow.add_link('1_2', '1', '2')
        self.flow.add_link('2_3', '2', '3')
        self.flow.add_link('3_0', '3', '0')

        self.mobility.add_node('0')
        self.mobility.add_node('1')
        self.mobility.add_node('2')
        self.mobility.add_node('3')

        self.mobility.add_link('0_1', '0', '1', {})
        self.mobility.add_link('1_2', '1', '2', {})
        self.mobility.add_link('2_3', '2', '3', {})
        self.mobility.add_link('3_0', '3', '0', {})

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_subgraph_flow(self):
        subgraph = self.flow.extract_subgraph(['0', '1', '2'])

        self.assertEqual(list(subgraph.nodes.keys()), ['0', '1', '2'])
        self.assertEqual(list(subgraph.links.keys()), [('0', '1'), ('1', '2')])

    def test_subgraph_mobility(self):
        subgraph = self.mobility.extract_subgraph(['0', '1', '2'])

        self.assertEqual(list(subgraph.nodes.keys()), ['0', '1', '2'])
        self.assertEqual(list(subgraph.links.keys()), [('0', '1'), ('1', '2')])