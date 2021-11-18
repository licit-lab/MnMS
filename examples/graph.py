from routeservice.graph.graph import MultiModalGraph
from routeservice.graph.shortest_path import astar_multi_edge, dijkstra_multi_edge


mmgraph = MultiModalGraph()

mmgraph.flow_graph.add_node('0', [0, 0])
mmgraph.flow_graph.add_node('1', [1, 0])
mmgraph.flow_graph.add_node('2', [1, 1])
mmgraph.flow_graph.add_node('3', [0, 1])

mmgraph.flow_graph.add_link('0_1', '0', '1')
mmgraph.flow_graph.add_link('1_0', '1', '0')

mmgraph.flow_graph.add_link('1_2', '1', '2')
mmgraph.flow_graph.add_link('2_1', '2', '1')

mmgraph.flow_graph.add_link('2_3', '2', '3')
mmgraph.flow_graph.add_link('3_2', '3', '2')

mmgraph.flow_graph.add_link('3_1', '3', '1')
mmgraph.flow_graph.add_link('1_3', '1', '3')


bus_service = mmgraph.add_mobility_service('Bus')
car_service = mmgraph.add_mobility_service('Car')

bus_service.add_node('0')
bus_service.add_node('1')
bus_service.add_node('2')

bus_service.add_link('BUS_0_2', '0', '2', {'time': 10.3}, reference_links=[])
bus_service.add_link('BUS_0_1', '0', '1', {'time': 5.5}, reference_links=['0_1'])

car_service.add_node('0')
car_service.add_node('1')
car_service.add_node('2')
car_service.add_node('3')

car_service.add_link('CAR_0_1', '0', '1', {'time': 5.1}, reference_links=['0_1'])
car_service.add_link('CAR_1_0', '1', '0', {'time': 5.1}, reference_links=['1_0'])
car_service.add_link('CAR_1_2', '1', '2', {'time': 5.1}, reference_links=['1_2'])
car_service.add_link('CAR_2_1', '2', '1', {'time': 5.1}, reference_links=['2_1'])
car_service.add_link('CAR_2_3', '2', '3', {'time': 5.1}, reference_links=['2_3'])
car_service.add_link('CAR_3_2', '3', '2', {'time': 5.1}, reference_links=['3_2'])
car_service.add_link('CAR_3_1', '3', '1', {'time': 5.1}, reference_links=['3_1'])
car_service.add_link('CAR_1_3', '1', '3', {'time': 5.1}, reference_links=['1_3'])


# print(astar(mmgraph.mobility_graph, '0', '2', lambda x: 0, cost='time'))
print(dijkstra_multi_edge(mmgraph.mobility_graph, '0', '2', cost='time'))
print(astar_multi_edge(mmgraph.mobility_graph, '0', '2', lambda x:0, cost='time'))
