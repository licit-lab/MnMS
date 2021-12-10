from mnms.graph.core import MultiModalGraph
from mnms.tools.time import TimeTable, Time
from mnms.mobility_service import BaseMobilityService, PublicTransport
from mnms.log import logger, LOGLEVEL
from mnms.graph.algorithms.shortest_path import dijkstra
from mnms.tools.render import draw_flow_graph

import matplotlib.pyplot as plt

'''
              O*********O  |
            *           *  |
          *             *  | BUS
        *               *  |
O******O*********O******O  |
    *  *                  
  O    *                
       *              
O******O*********O******O  | TRAM

'''


logger.setLevel(LOGLEVEL.DEBUG)

mmgraph = MultiModalGraph()

flow_graph = mmgraph.flow_graph

flow_graph.add_node('0', [0, 0])
flow_graph.add_node('1', [1, 0])
flow_graph.add_node('2', [2, 0])
flow_graph.add_node('3', [3, 0])

flow_graph.add_node('4', [0.5, 0.5])
flow_graph.add_node('5', [1, 1])
flow_graph.add_node('6', [1.5, 2])
flow_graph.add_node('7', [3, 2])

flow_graph.add_node('8', [0, 1])
flow_graph.add_node('9', [2, 1])
flow_graph.add_node('10', [3, 1])

flow_graph.add_link('0_1', '0', '1')
flow_graph.add_link('1_2', '1', '2')
flow_graph.add_link('2_3', '2', '3')
flow_graph.add_link('1_5', '1', '5')
flow_graph.add_link('4_5', '4', '5')
flow_graph.add_link('8_5', '8', '5')
flow_graph.add_link('5_9', '5', '9')
flow_graph.add_link('9_10', '9', '10')
flow_graph.add_link('5_6', '5', '6')
flow_graph.add_link('6_7', '6', '7')
flow_graph.add_link('10_7', '10', '7')
flow_graph.add_link('3_10', '3', '10')

# fig,ax = plt.subplots()
# draw_flow_graph(ax, flow_graph)
# plt.show()


tram = BaseMobilityService('TRAM', 10)
tram.add_node('0', '0')
tram.add_node('1', '1')
tram.add_node('2', '2')
tram.add_node('3', '3')

tram.add_link('0_1', '0', '1', {'time':1}, ['0_1'], [0])
tram.add_link('1_2', '1', '2', {'time':1}, ['1_2'], [0])
tram.add_link('2_3', '2', '3', {'time':1}, ['2_3'], [0])


bus = PublicTransport('BUS', 8.3)

l0 = bus.add_line('L0', TimeTable.create_table_freq("07:00:00", "18:00:00", delta_min=15))
l0.add_start_stop('8', '8')
l0.add_stop('5', '5')
l0.add_stop('9', '9')
l0.add_stop('10', '10')
l0.add_end_stop('7', '7')

l0.connect_stops('8_5', '8', '5', 100, reference_links='8_5', reference_lane_ids=[0])
l0.connect_stops('5_9', '5', '9', 100, reference_links='5_9', reference_lane_ids=[0])
l0.connect_stops('9_10', '9', '10', 100, reference_links='9_10', reference_lane_ids=[0])
l0.connect_stops('10_7', '10', '7', 10000, reference_links='10_7', reference_lane_ids=[0])

l1 = bus.add_line('L1', TimeTable.create_table_freq("07:00:00", "18:00:00", delta_min=15))
l1.add_start_stop('4', '4')
l1.add_stop('5', '5')
l1.add_stop('6', '6')
l1.add_end_stop('7', '7')

l1.connect_stops('4_5', '4', '5', 100, reference_links='4_5', reference_lane_ids=[0])
l1.connect_stops('5_6', '5', '6', 100, reference_links='5_6', reference_lane_ids=[0])
l1.connect_stops('6_7', '6', '7', 100, reference_links='6_7', reference_lane_ids=[0])

bus.connect_lines('L0', 'L1', '5')
bus.update_costs(Time('08:00:00'))

# for lid in bus.lines['L0'].links:
#     nodes = bus._map_lid_nodes['L0_' + lid]
#     link = bus.links[nodes]
#     print(link.id, link.costs)

#
mmgraph.mobility_graph.add_topo_graph('TRAM', tram)
mmgraph.mobility_graph.add_topo_graph('BUS', bus)

mmgraph.mobility_graph.connect_topo_graphs('TRAM_BUS', '1', 'L0_5', {'time': 1})


# print(mmgraph.mobility_graph.links[('L1_5', 'L0_5')].costs)


# print(mmgraph.mobility_graph.nodes)
# print(mmgraph.mobility_graph.links)
print(mmgraph.mobility_graph._adjacency)
print(dijkstra(mmgraph.mobility_graph, '0', 'L0_7', cost='time'))


