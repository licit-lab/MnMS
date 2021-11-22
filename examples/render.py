from symumaas.graph import MultiModalGraph
from symumaas.graph.render import draw_flow_graph, draw_mobility_service

import matplotlib.pyplot as plt

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

mmgraph.flow_graph.add_link('3_1', '3', '0')
mmgraph.flow_graph.add_link('1_3', '0', '3')

bus_service = mmgraph.add_mobility_service('Bus')
car_service = mmgraph.add_mobility_service('Car')
uber_service = mmgraph.add_mobility_service('Uber')

bus_service.add_node('0')
bus_service.add_node('1')
bus_service.add_node('2')

bus_service.add_link('BUS_0_1', '0', '1', {'time': 5.5}, reference_links=['0_1'])
bus_service.add_link('BUS_1_2', '1', '2', {'time': 50.5}, reference_links=['1_2'])
bus_service.add_link('BUS_0_2', '0', '2', {'time': 10.3}, reference_links=[])

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

uber_service.add_link('UBER_0_1', '0', '1', {'time': 1}, reference_links=['0_1'])

mmgraph.connect_mobility_service('Bus', 'Car', '0', {'time': 2})
mmgraph.connect_mobility_service('Car', 'Bus', '0', {'time': 2})
mmgraph.connect_mobility_service('Bus', 'Uber', '0', {'time': 4})
mmgraph.connect_mobility_service('Uber', 'Bus', '0', {'time': 2})
mmgraph.connect_mobility_service('Uber', 'Car', '0', {'time': 2})
mmgraph.connect_mobility_service('Car', 'Uber', '0', {'time': 2})

mmgraph.connect_mobility_service('Bus', 'Car', '1', {'time': 2})
mmgraph.connect_mobility_service('Car', 'Bus', '1', {'time': 2})
mmgraph.connect_mobility_service('Bus', 'Uber', '1', {'time': 4})
mmgraph.connect_mobility_service('Uber', 'Bus', '1', {'time': 2})
mmgraph.connect_mobility_service('Uber', 'Car', '1', {'time': 2})
mmgraph.connect_mobility_service('Car', 'Uber', '1', {'time': 2})

mmgraph.connect_mobility_service('Bus', 'Car', '2', {'time': 2});
mmgraph.connect_mobility_service('Car', 'Bus', '2', {'time': 2})
mmgraph.connect_mobility_service('Bus', 'Uber', '2', {'time': 4})
mmgraph.connect_mobility_service('Uber', 'Bus', '2', {'time': 2})
mmgraph.connect_mobility_service('Uber', 'Car', '2', {'time': 2})
mmgraph.connect_mobility_service('Car', 'Uber', '2', {'time': 2})


fig, ax = plt.subplots()
draw_mobility_service(ax, mmgraph, 'Bus', 'red', linkwidth=4, nodesize=10)
draw_mobility_service(ax, mmgraph, 'Car', 'green', linkwidth=3, nodesize=8)
draw_flow_graph(ax, mmgraph.flow_graph, color='black', linkwidth=2, nodesize=6)

plt.show()