import unittest

from mnms.graph.core import MultiModalGraph
from mnms.graph.algorithms import compute_shortest_path
from mnms.graph.path import reconstruct_path


class TestPath(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

        self.mmgraph = MultiModalGraph()
        flow = self.mmgraph.flow_graph
        mobility = self.mmgraph.mobility_graph

        flow.add_node('0', [0, 0])
        flow.add_node('1', [1, 0])
        flow.add_node('2', [2, 0])
        flow.add_node('3', [3, 0])

        flow.add_link('0_1', '0', '1')
        flow.add_link('1_2', '1', '2')
        flow.add_link('2_3', '2', '3')

        self.mmgraph.add_sensor('Res1', ['0_1', '1_2'])
        self.mmgraph.add_sensor('Res2', ['2_3'])

        m1 = self.mmgraph.add_mobility_service('M1')
        m1.add_node('0', '0')
        m1.add_node('1', '1')
        m1.add_link('M1_0_1', '0', '1', {'time': 1}, ['0_1'])

        m2 = self.mmgraph.add_mobility_service('M2')
        m2.add_node('0', '0')
        m2.add_node('1', '1')
        m2.add_node('3', '3')
        m2.add_link('M2_0_1', '0', '1', {'time': 10}, ['0_1'])
        m2.add_link('M2_1_3', '1', '3', {'time': 20}, ['1_2', '2_3'])

        self.mmgraph.connect_mobility_service('M1', 'M2', '1', {"time": 0})

        cost, self.path = compute_shortest_path(self.mmgraph, '0', '3', cost='time')

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_reconstruct(self):
        reconstructed = reconstruct_path(self.mmgraph, self.path)
        self.assertDictEqual(reconstructed[0], {'sensor': 'Res1', 'mode': 'M1', 'length': 1.0})
        self.assertDictEqual(reconstructed[1], {'sensor': 'Res1', 'mode': 'M2', 'length': 1.0})
        self.assertDictEqual(reconstructed[2], {'sensor': 'Res2', 'mode': 'M2', 'length': 1.0})
