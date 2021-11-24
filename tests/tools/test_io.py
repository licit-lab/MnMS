import unittest

from tempfile import TemporaryDirectory

from mnms.graph.core import MultiModalGraph
from mnms.tools.io import save_graph, load_graph


class TestIO(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.tempfile = TemporaryDirectory()
        self.pathdir = self.tempfile.name+'/'

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

        self.mmgraph.add_reservoir('Res', ['0_1', '1_2'])

        serv1 = self.mmgraph.add_mobility_service("s1")
        serv2 = self.mmgraph.add_mobility_service("s2")

        serv1.add_node('0')
        serv1.add_node('1')
        serv1.add_link('SERV1_0_1', '0', '1', {'test':0})

        serv2.add_node('1')
        serv2.add_node('2')
        serv2.add_link('SERV2_0_1', '1', '2', {'test': 1})

        self.mmgraph.connect_mobility_service('s1', 's2', '1', {'test': 2})

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.tempfile.cleanup()

    def test_save_load(self):
        save_graph(self.mmgraph, self.pathdir+'test.json')
        new_graph = load_graph(self.pathdir+'test.json')

        self.assertEqual(self.mmgraph.flow_graph.nodes.keys(), new_graph.flow_graph.nodes.keys())

        old_pos = [self.mmgraph.flow_graph.nodes[i].pos for i in self.mmgraph.flow_graph.nodes]
        new_pos = [new_graph.flow_graph.nodes[i].pos for i in self.mmgraph.flow_graph.nodes]

        for opos, npos in zip(old_pos, new_pos):
            self.assertCountEqual(opos, npos)

        for l in self.mmgraph.flow_graph.links:
            old_link = self.mmgraph.flow_graph.links[l]
            new_link = new_graph.flow_graph.links[l]
            self.assertTrue(old_link.id == new_link.id)
            self.assertTrue(old_link.upstream_node == new_link.upstream_node)
            self.assertTrue(old_link.downstream_node == new_link.downstream_node)

        self.assertTrue('s1' in new_graph._mobility_services)
        self.assertTrue('s2' in new_graph._mobility_services)

        self.assertEqual(self.mmgraph.mobility_graph.nodes.keys(), new_graph.mobility_graph.nodes.keys())

        for l in self.mmgraph.mobility_graph.links:
            old_link = self.mmgraph.mobility_graph.links[l]
            new_link = new_graph.mobility_graph.links[l]
            self.assertTrue(old_link.id == new_link.id)
            self.assertTrue(old_link.upstream_node == new_link.upstream_node)
            self.assertTrue(old_link.downstream_node == new_link.downstream_node)
            self.assertDictEqual(old_link.costs, new_link.costs)


        self.assertEqual(list(new_graph.reservoirs.keys()), ['Res'])