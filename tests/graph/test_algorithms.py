import unittest

from routeservice.graph import MultiModalGraph
from routeservice.graph.algorithms import dijkstra, astar

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

        bus_service = self.mmgraph.add_mobility_service('Bus')
        car_service = self.mmgraph.add_mobility_service('Car')
        uber_service = self.mmgraph.add_mobility_service('Uber')

        bus_service.add_node('0')
        bus_service.add_node('1')
        bus_service.add_node('2')

        bus_service.add_link('BUS_0_1', '0', '1', {'time': 1.5}, reference_links=['0_1'])
        bus_service.add_link('BUS_1_2', '1', '2', {'time': 5.5}, reference_links=['1_2'])
        bus_service.add_link('BUS_0_2', '0', '2', {'time': 1.3}, reference_links=[])

        car_service.add_node('0')
        car_service.add_node('1')
        car_service.add_node('2')
        car_service.add_node('3')

        car_service.add_link('CAR_0_1', '0', '1', {'time': 15.1}, reference_links=['0_1'])
        car_service.add_link('CAR_1_0', '1', '0', {'time': 5.1}, reference_links=['1_0'])
        car_service.add_link('CAR_1_2', '1', '2', {'time': 7.1}, reference_links=['1_2'])
        car_service.add_link('CAR_2_1', '2', '1', {'time': 5.1}, reference_links=['2_1'])
        car_service.add_link('CAR_2_3', '2', '3', {'time': 5.1}, reference_links=['2_3'])
        car_service.add_link('CAR_3_2', '3', '2', {'time': 5.1}, reference_links=['3_2'])
        car_service.add_link('CAR_3_1', '3', '1', {'time': 5.1}, reference_links=['3_1'])
        car_service.add_link('CAR_1_3', '1', '3', {'time': 5.1}, reference_links=['1_3'])

        uber_service.add_node('0')
        uber_service.add_node('1')

        uber_service.add_link('UBER_0_1', '0', '1', {'time': 100}, reference_links=['0_1'])

        self.mmgraph.connect_mobility_service('Bus', 'Car', '0', {'time': 2})
        self.mmgraph.connect_mobility_service('Car', 'Bus', '0', {'time': 2})
        self.mmgraph.connect_mobility_service('Bus', 'Uber', '0', {'time': 4})
        self.mmgraph.connect_mobility_service('Uber', 'Bus', '0', {'time': 2})
        self.mmgraph.connect_mobility_service('Uber', 'Car', '0', {'time': 2})
        self.mmgraph.connect_mobility_service('Car', 'Uber', '0', {'time': 2})

        self.mmgraph.connect_mobility_service('Bus', 'Car', '1', {'time': 2})
        self.mmgraph.connect_mobility_service('Car', 'Bus', '1', {'time': 2})
        self.mmgraph.connect_mobility_service('Bus', 'Uber', '1', {'time': 4})
        self.mmgraph.connect_mobility_service('Uber', 'Bus', '1', {'time': 2})
        self.mmgraph.connect_mobility_service('Uber', 'Car', '1', {'time': 2})
        self.mmgraph.connect_mobility_service('Car', 'Uber', '1', {'time': 2})

        self.mmgraph.connect_mobility_service('Bus', 'Car', '2', {'time': 2})
        self.mmgraph.connect_mobility_service('Car', 'Bus', '2', {'time': 2})
        self.mmgraph.connect_mobility_service('Bus', 'Uber', '2', {'time': 4})
        self.mmgraph.connect_mobility_service('Uber', 'Bus', '2', {'time': 2})
        self.mmgraph.connect_mobility_service('Uber', 'Car', '2', {'time': 2})
        self.mmgraph.connect_mobility_service('Car', 'Uber', '2', {'time': 2})

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_dijkstra(self):
        cost, path = dijkstra(self.mmgraph.mobility_graph, 'Bus_0', 'Bus_2', cost='time')
        self.assertListEqual(list(path), ['Bus_0', 'Bus_2'])
        self.assertEqual(self.mmgraph.mobility_graph.links[('Bus_0', 'Bus_2')].costs['time'], cost)

        self.mmgraph.mobility_graph.links[('Bus_0', 'Bus_2')].costs['time'] = 1e10
        cost, path = dijkstra(self.mmgraph.mobility_graph, 'Bus_0', 'Bus_2', cost='time')

        self.assertListEqual(list(path), ['Bus_0', 'Bus_1', 'Bus_2'])
        self.assertEqual(self.mmgraph.mobility_graph.links[('Bus_0', 'Bus_1')].costs['time']+self.mmgraph.mobility_graph.links[('Bus_1', 'Bus_2')].costs['time'], cost)

