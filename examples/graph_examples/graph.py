from mnms.log import set_log_level, LOGLEVEL
from mnms.graph import MultiModalGraph

set_log_level(LOGLEVEL.DEBUG)
mmgraph = MultiModalGraph()

mmgraph.flow_graph.add_node('0', [0, 0])
mmgraph.flow_graph.add_node('1', [1, 0])
mmgraph.flow_graph.add_node('2', [1, 1])
mmgraph.flow_graph.add_node('3', [0, 1])

mmgraph.flow_graph._add_link('0_1')
mmgraph.flow_graph._add_link('1_0')

mmgraph.flow_graph._add_link('1_2')
mmgraph.flow_graph._add_link('2_1')

mmgraph.flow_graph._add_link('2_3')
mmgraph.flow_graph._add_link('3_2')

mmgraph.flow_graph._add_link('3_1')
mmgraph.flow_graph._add_link('1_3')

bus_service = mmgraph.add_mobility_service('Bus')
car_service = mmgraph.add_mobility_service('Car')
uber_service = mmgraph.add_mobility_service('Uber')

bus_service.add_node('0')
bus_service.add_node('1')
bus_service.add_node('2')

bus_service._add_link('BUS_0_1')
bus_service._add_link('BUS_1_2')
bus_service._add_link('BUS_0_2')

car_service.add_node('0')
car_service.add_node('1')
car_service.add_node('2')
car_service.add_node('3')

car_service._add_link('CAR_0_1')
car_service._add_link('CAR_1_0')
car_service._add_link('CAR_1_2')
car_service._add_link('CAR_2_1')
car_service._add_link('CAR_2_3')
car_service._add_link('CAR_3_2')
car_service._add_link('CAR_3_1')
car_service._add_link('CAR_1_3')

uber_service.add_node('0')
uber_service.add_node('1')

uber_service._add_link('UBER_0_1')

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

mmgraph.connect_mobility_service('Bus', 'Car', '2', {'time': 2})
mmgraph.connect_mobility_service('Car', 'Bus', '2', {'time': 2})
mmgraph.connect_mobility_service('Bus', 'Uber', '2', {'time': 4})
mmgraph.connect_mobility_service('Uber', 'Bus', '2', {'time': 2})
mmgraph.connect_mobility_service('Uber', 'Car', '2', {'time': 2})
mmgraph.connect_mobility_service('Car', 'Uber', '2', {'time': 2})

mmgraph.add_zone('Res', [link for link in mmgraph.flow_graph.links.values()])

print([l.sensor for l in mmgraph.flow_graph.links.values()])
