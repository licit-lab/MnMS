import unittest

from mnms.graph import MultiModalGraph
from mnms.graph.algorithms import nearest_mobility_service
from mnms.graph.algorithms.shortest_path import astar, dijkstra
from mnms.graph.algorithms.walk import walk_connect
from mnms.mobility_service import BaseMobilityService


class TestAlgorithms(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.mmgraph = MultiModalGraph()

        self.mmgraph.flow_graph.add_node('0', [0, 0])
        self.mmgraph.flow_graph.add_node('1', [1, 0])
        self.mmgraph.flow_graph.add_node('2', [1, 1])
        self.mmgraph.flow_graph.add_node('3', [0, 1])

        self.mmgraph.flow_graph.add_link('0_1', '0', '1')
        self.mmgraph.flow_graph.add_link('1_0', '1', '0')

        self.mmgraph.flow_graph.add_link('1_2', '1', '2')
        self.mmgraph.flow_graph.add_link('2_1', '2', '1')

        self.mmgraph.flow_graph.add_link('2_3', '2', '3')
        self.mmgraph.flow_graph.add_link('3_2', '3', '2')

        self.mmgraph.flow_graph.add_link('3_1', '3', '1')
        self.mmgraph.flow_graph.add_link('1_3', '1', '3')

        bus_service = BaseMobilityService('Bus', 10)
        car_service = BaseMobilityService('Car', 10)
        uber_service = BaseMobilityService('Uber', 10)

        bus_service.add_node('B0', '0')
        bus_service.add_node('B1', '1')
        bus_service.add_node('B2', '2')

        bus_service.add_link('BUS_0_1', 'B0', 'B1', {'time': 1.5}, reference_links=['0_1'])
        bus_service.add_link('BUS_1_2', 'B1', 'B2', {'time': 5.5}, reference_links=['1_2'])
        bus_service.add_link('BUS_0_2', 'B0', 'B2', {'time': 1.3}, reference_links=[])

        car_service.add_node('C0', '0')
        car_service.add_node('C1', '1')
        car_service.add_node('C2', '2')
        car_service.add_node('C3', '3')

        car_service.add_link('CAR_0_1', 'C0', 'C1', {'time': 15.1}, reference_links=['0_1'])
        car_service.add_link('CAR_1_0', 'C1', 'C0', {'time': 5.1}, reference_links=['1_0'])
        car_service.add_link('CAR_1_2', 'C1', 'C2', {'time': 7.1}, reference_links=['1_2'])
        car_service.add_link('CAR_2_1', 'C2', 'C1', {'time': 5.1}, reference_links=['2_1'])
        car_service.add_link('CAR_2_3', 'C2', 'C3', {'time': 5.1}, reference_links=['2_3'])
        car_service.add_link('CAR_3_2', 'C3', 'C2', {'time': 5.1}, reference_links=['3_2'])
        car_service.add_link('CAR_3_1', 'C3', 'C1', {'time': 5.1}, reference_links=['3_1'])
        car_service.add_link('CAR_1_3', 'C1', 'C3', {'time': 5.1}, reference_links=['1_3'])

        uber_service.add_node('U0', '0')
        uber_service.add_node('U1', '1')

        uber_service.add_link('UBER_0_1', 'U0', 'U1', {'time': 100}, reference_links=['0_1'])

        self.mmgraph.add_mobility_service(bus_service)
        self.mmgraph.add_mobility_service(uber_service)
        self.mmgraph.add_mobility_service(car_service)

        self.mmgraph.connect_mobility_service('Bus_Car_0', 'B0', 'C0', {'time': 2})
        self.mmgraph.connect_mobility_service('Car_Bus_0', 'C0', 'B0', {'time': 2})
        self.mmgraph.connect_mobility_service('Bus_Uber_0', 'B0', 'U0', {'time': 4})
        self.mmgraph.connect_mobility_service('Uber_Bus_0', 'U0', 'B0', {'time': 2})
        self.mmgraph.connect_mobility_service('Uber_Car_0', 'U0', 'C0', {'time': 2})
        self.mmgraph.connect_mobility_service('Car_Uber_0', 'C0', 'U0', {'time': 2})

        self.mmgraph.connect_mobility_service('Bus_Car_1', 'B1', 'C1', {'time': 2})
        self.mmgraph.connect_mobility_service('Car_Bus_1', 'C1', 'B1', {'time': 2})
        self.mmgraph.connect_mobility_service('Bus_Uber_1', 'B1', 'U1', {'time': 4})
        self.mmgraph.connect_mobility_service('Uber_Bus_1', 'U1', 'B1', {'time': 2})
        self.mmgraph.connect_mobility_service('Uber_Car_1', 'U1', 'C1', {'time': 2})
        self.mmgraph.connect_mobility_service('Car_Uber_1', 'C1', 'U1', {'time': 2})

        self.mmgraph.connect_mobility_service('Bus_Car_2', 'B2', 'C2', {'time': 2})
        self.mmgraph.connect_mobility_service('Car_Bus_2', 'C2', 'B2', {'time': 2})


    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_dijkstra(self):
        cost, path = dijkstra(self.mmgraph.mobility_graph, 'B0', 'B2', cost='time')
        self.assertListEqual(list(path), ['B0', 'B2'])
        self.assertEqual(self.mmgraph.mobility_graph.links[('B0', 'B2')].costs['time'], cost)

        self.mmgraph.mobility_graph.links[('B0', 'B2')].costs['time'] = 1e10
        cost, path = dijkstra(self.mmgraph.mobility_graph, 'B0', 'B2', cost='time')

        self.assertListEqual(list(path), ['B0', 'B1', 'B2'])
        self.assertEqual(self.mmgraph.mobility_graph.links[('B0', 'B1')].costs['time']+self.mmgraph.mobility_graph.links[('B1', 'B2')].costs['time'], cost)

    def test_nearest_mobility(self):
        pos = [10, 10]
        node = nearest_mobility_service(pos, self.mmgraph, 'Bus')
        self.assertEqual(node, '2')

        node = nearest_mobility_service(pos, self.mmgraph, 'Uber')
        self.assertEqual(node, '1')

    def test_walk(self):
        mmgraph = MultiModalGraph()

        mmgraph.flow_graph.add_node('0', [-1, 0])
        mmgraph.flow_graph.add_node('1', [0, 0])
        mmgraph.flow_graph.add_node('2', [1, 0])
        mmgraph.flow_graph.add_node('3', [-0.8, -0.5])
        mmgraph.flow_graph.add_node('4', [0.99, -0.5])
        mmgraph.flow_graph.add_link('0_1', '0', '1')
        mmgraph.flow_graph.add_link('1_2', '1', '2')
        mmgraph.flow_graph.add_link('3_4', '3', '4')

        serv1 = BaseMobilityService('SERV1', 10)
        serv1.add_node('S10', '0')
        serv1.add_node('S11', '1')
        serv1.add_node('S12', '2')

        serv1.add_link('0_1', 'S10', 'S11', {'time': 1}, '0_1', [0])
        serv1.add_link('1_2', 'S11', 'S12', {'time': 1}, '1_2', [0])

        serv2 = BaseMobilityService('SERV2', 10)
        serv2.add_node('S23', '3')
        serv2.add_node('S24', '4')

        serv2.add_link('3_4', 'S23', 'S24', {'time': 1}, '3_4', [0])

        mmgraph.add_mobility_service(serv1)
        mmgraph.add_mobility_service(serv2)

        mmgraph.mobility_graph.check()

        walk_connect(mmgraph, radius=0.71, walk_speed=1.4)

        self.assertTrue(("S10", "S23") in mmgraph.mobility_graph.links)
        self.assertTrue(("S23", "S10") in mmgraph.mobility_graph.links)
        self.assertTrue(("S24", "S12") in mmgraph.mobility_graph.links)
        self.assertTrue(("S12", "S24") in mmgraph.mobility_graph.links)

        self.assertAlmostEqual(0.7001399860027991, mmgraph.mobility_graph.links[("S24", "S12")].costs['time'])
        self.assertAlmostEqual(0.7539230729988307, mmgraph.mobility_graph.links[("S10", "S23")].costs['time'])
