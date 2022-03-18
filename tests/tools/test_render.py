import unittest

import matplotlib.pyplot as plt

from mnms.graph.core import MultiModalGraph
from mnms.mobility_service.car import PersonalCar
from mnms.tools.render import draw_flow_graph, draw_multimodal_graph, draw_path


class TestRender(unittest.TestCase):
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

        serv1 = PersonalCar("s1", 10)
        serv2 = PersonalCar("s2", 9)

        serv1.add_node('S1_0', '0')
        serv1.add_node('S1_1', '1')
        serv1.add_link('SERV1_0_1', 'S1_0', 'S1_1', {'test':0})

        serv2.add_node('S2_1', '1')
        serv2.add_node('S2_2', '2')
        serv2.add_link('SERV2_0_1', 'S2_1', 'S2_2', {'test': 1})

        self.mmgraph.add_mobility_service(serv1)
        self.mmgraph.add_mobility_service(serv2)
        self.mmgraph.connect_mobility_service('S1_S2_1', 'S1_1', 'S2_1', 0, serv2.connect_to_service('S2_1'))

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_draw_flow_graph(self):
        fig, ax = plt.subplots()
        draw_flow_graph(ax, self.mmgraph.flow_graph)

    def test_draw_mmgraph(self):
        fig, ax = plt.subplots()
        draw_multimodal_graph(ax, self.mmgraph)

    def test_draw_path(self):
        fig, ax = plt.subplots()
        draw_path(ax, self.mmgraph, ['S1_0', 'S1_1'])