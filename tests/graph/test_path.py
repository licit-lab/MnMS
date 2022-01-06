import unittest

from mnms.graph.core import MultiModalGraph
from mnms.graph.algorithms import compute_shortest_path
from mnms.graph.path import reconstruct_path
from mnms.mobility_service import BaseMobilityService


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

        self.mmgraph.add_zone('Res1', ['0_1', '1_2'])
        self.mmgraph.add_zone('Res2', ['2_3'])

        m1 = BaseMobilityService('M1', 10)
        m1.add_node('M1_0', '0')
        m1.add_node('M1_1', '1')
        m1.add_link('M1_0_1', 'M1_0', 'M1_1', {'time': 1}, ['0_1'])

        m2 = BaseMobilityService('M2', 10)
        m2.add_node('M2_0', '0')
        m2.add_node('M2_1', '1')
        m2.add_node('M2_3', '3')
        m2.add_link('M2_0_1', 'M2_0', 'M2_1', {'time': 10}, ['0_1'])
        m2.add_link('M2_1_3', 'M2_1', 'M2_3', {'time': 20}, ['1_2', '2_3'])

        self.mmgraph.add_mobility_service(m1)
        self.mmgraph.add_mobility_service(m2)

        self.mmgraph.connect_mobility_service('M1_M2_1', 'M1_1', 'M2_1', {"time": 0})

        cost, self.path = compute_shortest_path(self.mmgraph, '0', '3')
        print(self.path)

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_reconstruct(self):
        reconstructed = reconstruct_path(self.mmgraph, self.path)
        self.assertDictEqual(reconstructed[0], {'sensor': 'Res1', 'mode': 'M1', 'length': 1.0})
        self.assertDictEqual(reconstructed[1], {'sensor': 'Res1', 'mode': 'M2', 'length': 1.0})
        self.assertDictEqual(reconstructed[2], {'sensor': 'Res2', 'mode': 'M2', 'length': 1.0})
