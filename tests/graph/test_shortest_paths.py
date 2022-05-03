import unittest

import numpy as np

from mnms.graph import MultiModalGraph
from mnms.graph.search import nearest_mobility_service
from mnms.graph.shortest_path import (astar, dijkstra, _euclidian_dist, compute_shortest_path,
                                      compute_n_best_shortest_path, bidirectional_dijkstra)
from mnms.graph.edition import walk_connect
from mnms.mobility_service.car import CarMobilityGraphLayer, PersonalCarMobilityService, OnDemandCarMobilityService
from mnms.demand.user import User
from mnms.mobility_service.public_transport import BusMobilityGraphLayer, PublicTransportMobilityService
from mnms.tools.time import TimeTable, Dt


class TestAlgorithms(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        mmgraph = MultiModalGraph()

        flow_graph = mmgraph.flow_graph

        flow_graph.add_node('0', [0, 0])
        flow_graph.add_node('1', [1, 0])
        flow_graph.add_node('2', [3, 0])
        flow_graph.add_node('3', [1, 1])
        flow_graph.add_node('4', [0, 1])

        flow_graph.add_link('0_1', '0', '1')
        flow_graph.add_link('1_2', '1', '2')
        flow_graph.add_link('1_3', '1', '3')
        flow_graph.add_link('3_2', '3', '2')
        flow_graph.add_link('4_3', '4', '3')
        flow_graph.add_link('0_4', '0', '4')

        car_layer = CarMobilityGraphLayer('Car',
                                          services=[PersonalCarMobilityService(),
                                                    OnDemandCarMobilityService('Uber')])

        car_layer.add_node('C0', '0')
        car_layer.add_node('C1', '1')
        car_layer.add_node('C2', '2')
        car_layer.add_node('C3', '3')
        car_layer.add_node('C4', '4')

        car_layer.add_link('C0_1', 'C0', 'C1', ['0_1'], {'travel_time':1})
        car_layer.add_link('C1_2', 'C1', 'C2', ['1_2'], {'travel_time':1})
        car_layer.add_link('C1_3', 'C1', 'C3', ['1_3'], {'travel_time':1})
        car_layer.add_link('C3_2', 'C3', 'C2', ['3_2'], {'travel_time':1})
        car_layer.add_link('C4_3', 'C4', 'C3', ['4_3'], {'travel_time':1})
        car_layer.add_link('C0_4', 'C0', 'C4', ['0_4'], {'travel_time':1})

        mmgraph.add_layer(car_layer)

        bus_layer = BusMobilityGraphLayer('Bus',
                                          7,
                                          services=[PublicTransportMobilityService('Bus')])

        bline = bus_layer.add_line('L1', TimeTable.create_table_freq('07:00:00', '09:00:00', Dt(minutes=10)))
        bline.add_stop('B0', '0')
        bline.add_stop('B1', '1')
        bline.add_stop('B2', '2')

        bline.connect_stops('B0_B1', 'B0', 'B1', 1, ['0_1'], {'travel_time':1.7})
        bline.connect_stops('B1_B2', 'B1', 'B2', 1, ['1_2'], {'travel_time':1.5})

        mmgraph.add_layer(bus_layer)

        mmgraph.connect_layers('C0_B0', 'C0', 'B0', 0, {'travel_time': 0})

        self.mmgraph = mmgraph

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_dijkstra(self):
        user = User(id='TEST', departure_time=None, origin='C0', destination='C2')
        path = dijkstra(self.mmgraph.mobility_graph, user.origin, user.destination, 'travel_time', user.available_mobility_service)
        self.assertListEqual(list(path.nodes), ['C0', 'C1', 'C2'])
        expected_cost = self.mmgraph.mobility_graph.links[('C0', 'C1')].costs['travel_time'] + \
                        self.mmgraph.mobility_graph.links[('C1', 'C2')].costs['travel_time']
        self.assertEqual(expected_cost, path.path_cost)

        self.mmgraph.mobility_graph.links[('C0', 'C1')].costs['travel_time'] = 1e10
        path = dijkstra(self.mmgraph.mobility_graph, user.origin, user.destination, 'travel_time',
                        user.available_mobility_service)

        self.assertListEqual(list(path.nodes), ['C0', 'C4', 'C3', 'C2'])

        expected_cost = self.mmgraph.mobility_graph.links[('C0', 'C4')].costs['travel_time'] + \
                        self.mmgraph.mobility_graph.links[('C4', 'C3')].costs['travel_time'] + \
                        self.mmgraph.mobility_graph.links[('C3', 'C2')].costs['travel_time']

        self.assertEqual(expected_cost, path.path_cost)

    def test_bidirectional_dijsktra(self):
        user = User(id='TEST', departure_time=None, origin='C0', destination='C2')
        path = bidirectional_dijkstra(self.mmgraph.mobility_graph, user.origin, user.destination, 'travel_time', user.available_mobility_service)
        self.assertListEqual(list(path.nodes), ['C0', 'C1', 'C2'])
        expected_cost = self.mmgraph.mobility_graph.links[('C0', 'C1')].costs['travel_time'] + \
                        self.mmgraph.mobility_graph.links[('C1', 'C2')].costs['travel_time']
        self.assertEqual(expected_cost, path.path_cost)

        self.mmgraph.mobility_graph.links[('C0', 'C1')].costs['travel_time'] = 1e10
        path = dijkstra(self.mmgraph.mobility_graph, user.origin, user.destination, 'travel_time',
                        user.available_mobility_service)

        self.assertListEqual(list(path.nodes), ['C0', 'C4', 'C3', 'C2'])

        expected_cost = self.mmgraph.mobility_graph.links[('C0', 'C4')].costs['travel_time'] + \
                        self.mmgraph.mobility_graph.links[('C4', 'C3')].costs['travel_time'] + \
                        self.mmgraph.mobility_graph.links[('C3', 'C2')].costs['travel_time']

        self.assertEqual(expected_cost, path.path_cost)

    def test_astar(self):
        user = User(id='TEST', departure_time=None, origin='C0', destination='C2')
        heuristic = lambda o, d, mmgraph=self.mmgraph: _euclidian_dist(o, d, mmgraph)
        path = astar(self.mmgraph.mobility_graph, user.origin, user.destination, 'travel_time',
                        user.available_mobility_service, heuristic)
        self.assertListEqual(list(path.nodes), ['C0', 'C1', 'C2'])
        expected_cost = self.mmgraph.mobility_graph.links[('C0', 'C1')].costs['travel_time'] + \
                        self.mmgraph.mobility_graph.links[('C1', 'C2')].costs['travel_time']
        self.assertEqual(expected_cost, path.path_cost)

        self.mmgraph.mobility_graph.links[('C0', 'C1')].costs['travel_time'] = 1e10
        path = dijkstra(self.mmgraph.mobility_graph, user.origin, user.destination, 'travel_time',
                        user.available_mobility_service)

        self.assertListEqual(list(path.nodes), ['C0', 'C4', 'C3', 'C2'])

        expected_cost = self.mmgraph.mobility_graph.links[('C0', 'C4')].costs['travel_time'] + \
                        self.mmgraph.mobility_graph.links[('C4', 'C3')].costs['travel_time'] + \
                        self.mmgraph.mobility_graph.links[('C3', 'C2')].costs['travel_time']

        self.assertEqual(expected_cost, path.path_cost)

    def test_compute_shortest_path_node(self):
        user = User(id='TEST', departure_time=None, origin='0', destination='2')
        path = compute_shortest_path(self.mmgraph, user, cost='travel_time')
        self.assertListEqual(list(path.nodes), ['C0', 'C1', 'C2'])
        self.mmgraph.mobility_graph.links[('C0', 'C1')].costs['travel_time'] = 1e10
        path = compute_shortest_path(self.mmgraph, user, cost='travel_time', algorithm='astar')

        self.assertListEqual(list(path.nodes), ['C0', 'C4', 'C3', 'C2'])

    def test_compute_nbest_shortest_path_node(self):
        user = User(id='TEST', departure_time=None, origin='0', destination='2')
        paths, costs = compute_n_best_shortest_path(self.mmgraph, user, 2, cost='travel_time')

        self.assertAlmostEqual(paths[0].path_cost, 2)
        self.assertListEqual(list(paths[0].nodes), ['C0', 'C1', 'C2'])

        self.assertAlmostEqual(paths[1].path_cost, 3)
        self.assertListEqual(list(paths[1].nodes), ['C0', 'C4', 'C3', 'C2'])

    def test_compute_nbest_shortest_path_coordinates(self):
        user = User(id='TEST', departure_time=None, origin=np.array([0, 0]), destination=np.array([3, 0]))
        paths, penalized_costs = compute_n_best_shortest_path(self.mmgraph,
                                                              user,
                                                              5,
                                                              cost='travel_time',
                                                              radius=0.1,
                                                              growth_rate_radius=1e-5)

        self.assertAlmostEqual(paths[0].path_cost, 2)
        self.assertListEqual(list(paths[0].nodes), ['C0', 'C1', 'C2'])

        self.assertAlmostEqual(paths[1].path_cost, 3)
        self.assertListEqual(list(paths[1].nodes), ['C0', 'C4', 'C3', 'C2'])

    def test_compute_shortest_path_coords(self):
        user = User(id='TEST', departure_time=None, origin=np.array([0, 0]), destination=np.array([3, 0]))
        path = compute_shortest_path(self.mmgraph, user, cost='travel_time', radius=0.1, growth_rate_radius=1e-5)

        self.assertAlmostEqual(path.path_cost, 2)
        self.assertListEqual(list(path.nodes), ['C0', 'C1', 'C2'])

    def test_nearest_mobility(self):
        pos = [10, 10]
        node = nearest_mobility_service(pos, self.mmgraph, 'Bus')
        self.assertEqual(node, '2')

        node = nearest_mobility_service(pos, self.mmgraph, 'Uber')
        self.assertEqual(node, '2')
