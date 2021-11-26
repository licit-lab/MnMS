from mnms.graph.algorithms import compute_shortest_path
from mnms.tools.time import Time

import numpy as np

def create_random_demand(mmgraph: "MultiModalGraph", tstart="07:00:00", tend="18:00:00", min_cost=float('inf'), cost_path=None, distrib_time=np.random.uniform):
    if cost_path is None:
        cost_path = "_default"

    tstart = Time(tstart).to_seconds()
    tend = Time(tend).to_seconds()

    demand = []
    extremities = mmgraph.get_extremities()
    for unode in extremities:
        for dnode in extremities:
            if unode != dnode:
                cost, path = compute_shortest_path(mmgraph, unode, dnode, cost_path)
                if cost < float("inf"):
                    if cost >= min_cost:
                        demand.append([Time.fromSeconds(distrib_time(tstart, tend)) ,(unode, dnode)])



    return demand



if __name__ == "__main__":
    from mnms.graph import MultiModalGraph
    from mnms.tools.render import draw_flow_graph, draw_mobility_service, draw_multimodal_graph
    from mnms.graph.path import reconstruct_path
    import matplotlib.pyplot as plt


    mmgraph = MultiModalGraph()
    fgraph = mmgraph.flow_graph

    fgraph.add_node('O_0', [-2, 1])
    fgraph.add_node('O_1', [-2, -1])
    fgraph.add_node('N_0', [-1, 2])
    fgraph.add_node('N_1', [1, 2])
    fgraph.add_node('E_0', [2, 1])
    fgraph.add_node('E_1', [2, -1])
    fgraph.add_node('S_0', [1, -2])
    fgraph.add_node('S_1', [-1, -2])
    fgraph.add_node('C_0', [-1, 1])
    fgraph.add_node('C_1', [1, 1])
    fgraph.add_node('C_2', [1, -1])
    fgraph.add_node('C_3', [-1, -1])


    fgraph.add_link('L0_0', 'O_0', 'C_0', 1)
    fgraph.add_link('L0_1', 'C_0', 'O_0', 1)

    fgraph.add_link('L1_0', 'C_0', 'C_1', 2)
    fgraph.add_link('L1_1', 'C_1', 'C_0', 2)

    fgraph.add_link('L2_0', 'C_1', 'E_0', 1)
    fgraph.add_link('L2_1', 'E_0', 'C_1', 1)

    # -------------------------------------

    fgraph.add_link('L3_0', 'O_1', 'C_3', 1)
    fgraph.add_link('L3_1', 'C_3', 'O_1', 1)

    fgraph.add_link('L4_0', 'C_3', 'C_2', 2)
    fgraph.add_link('L4_1', 'C_2', 'C_3', 2)

    fgraph.add_link('L5_0', 'C_2', 'E_1', 1)
    fgraph.add_link('L5_1', 'E_1', 'C_2', 1)

    # -------------------------------------

    fgraph.add_link('L6_0', 'N_0', 'C_0', 1)
    fgraph.add_link('L6_1', 'C_0', 'N_0', 1)

    fgraph.add_link('L7_0', 'C_0', 'C_3', 2)
    fgraph.add_link('L7_1', 'C_3', 'C_0', 2)

    fgraph.add_link('L8_0', 'C_3', 'S_1', 1)
    fgraph.add_link('L8_1', 'S_1', 'C_3', 1)

    # -------------------------------------

    fgraph.add_link('L9_0', 'N_1', 'C_1', 1)
    fgraph.add_link('L9_1', 'C_1', 'N_1', 1)

    fgraph.add_link('L10_0', 'C_1', 'C_2', 2)
    fgraph.add_link('L10_1', 'C_2', 'C_1', 2)

    fgraph.add_link('L11_0', 'C_2', 'S_0', 1)
    fgraph.add_link('L11_1', 'S_0', 'C_2', 1)

    # -------------------------------------

    m1 = mmgraph.add_mobility_service('M1')
    m1.add_node('0', 'O_0')
    m1.add_node('C0', 'C_0')
    m1.add_node('C3', 'C_1')
    m1.add_node('3', 'E_0')

    m1.add_link('M1_0_0', '0', 'C0', {'time': 1}, ['L0_0'])
    m1.add_link('M1_0_1', 'C0', '0', {'time': 1}, ['L0_1'])

    m1.add_link('M1_1_0', 'C0', 'C3', {'time': 2}, ['L1_0'])
    m1.add_link('M1_1_1', 'C3', 'C0', {'time': 2}, ['L1_1'])

    m1.add_link('M1_2_0', 'C3', '3', {'time': 1}, ['L2_0'])
    m1.add_link('M1_2_1', '3', 'C3', {'time': 1}, ['L2_1'])

    # -------------------------------------

    m2 = mmgraph.add_mobility_service('M2')
    m2.add_node('0', 'O_1')
    m2.add_node('C1', 'C_3')
    m2.add_node('C2', 'C_3')
    m2.add_node('3', 'E_1')

    m2.add_link('M2_0_0', '0', 'C1', {'time': 1}, ['L3_0'])
    m2.add_link('M2_0_1', 'C1', '0', {'time': 1}, ['L3_1'])

    m2.add_link('M2_1_0', 'C1', 'C2', {'time': 2}, ['L4_0'])
    m2.add_link('M2_1_1', 'C2', 'C1', {'time': 2}, ['L4_1'])

    m2.add_link('M2_2_0', 'C2', '3', {'time': 1}, ['L5_0'])
    m2.add_link('M2_2_1', '3', 'C2', {'time': 1}, ['L5_1'])

    # -------------------------------------

    m3 = mmgraph.add_mobility_service('M3')
    m3.add_node('0', 'N_0')
    m3.add_node('C0', 'C_0')
    m3.add_node('C1', 'C_3')
    m3.add_node('3', 'S_1')

    m3.add_link('M3_0_0', '0', 'C0', {'time': 1}, ['L6_0'])
    m3.add_link('M3_0_1', 'C0', '0', {'time': 1}, ['L6_1'])

    m3.add_link('M3_1_0', 'C0', 'C1', {'time': 2}, ['L7_0'])
    m3.add_link('M3_1_1', 'C1', 'C0', {'time': 2}, ['L7_1'])

    m3.add_link('M3_2_0', 'C1', '3', {'time': 1}, ['L8_0'])
    m3.add_link('M3_2_1', '3', 'C1', {'time': 1}, ['L8_1'])

    # -------------------------------------

    m4 = mmgraph.add_mobility_service('M4')
    m4.add_node('0', 'N_1')
    m4.add_node('C3', 'C_1')
    m4.add_node('C2', 'C_2')
    m4.add_node('3', 'S_0')

    m4.add_link('M4_0_0', '0', 'C3', {'time': 1}, ['L9_0'])
    m4.add_link('M4_0_1', 'C3', '0', {'time': 1}, ['L9_1'])

    m4.add_link('M4_1_0', 'C3', 'C2', {'time': 2}, ['L10_0'])
    m4.add_link('M4_1_1', 'C2', 'C3', {'time': 2}, ['L10_1'])

    m4.add_link('M4_2_0', 'C2', '3', {'time': 1}, ['L11_0'])
    m4.add_link('M4_2_1', '3', 'C2', {'time': 1}, ['L11_1'])

    # -------------------------------------

    mmgraph.connect_mobility_service('M1', 'M3', 'C0', {'time': 0})
    mmgraph.connect_mobility_service('M3', 'M1', 'C0', {'time': 0})
    # print(mmgraph.mobility_graph._adjacency['M1_C0'])

    mmgraph.connect_mobility_service('M1', 'M4', 'C3', {'time': 0})
    mmgraph.connect_mobility_service('M4', 'M1', 'C3', {'time': 0})

    mmgraph.connect_mobility_service('M2', 'M3', 'C1', {'time': 0})
    mmgraph.connect_mobility_service('M3', 'M2', 'C1', {'time': 0})

    mmgraph.connect_mobility_service('M2', 'M4', 'C2', {'time': 0})
    mmgraph.connect_mobility_service('M4', 'M2', 'C2', {'time': 0})

    demand = create_random_demand(mmgraph, min_cost=4)
    print(demand)
    print(len(demand))

    # cost, p = compute_shortest_path(mmgraph, 'O_0', 'E_1', 'time')
    # print(p)
    # print(reconstruct_path(mmgraph, p))
    # print(mmgraph.mobility_graph.nodes['M1_3'])

    # fig, ax = plt.subplots()
    # draw_flow_graph(ax, fgraph, linkwidth=2, nodesize=6, node_label=True)
    # draw_mobility_service(ax, mmgraph, 'M1', 'green')
    # draw_mobility_service(ax, mmgraph, 'M2', 'red')
    # draw_mobility_service(ax, mmgraph, 'M3', 'blue')
    # draw_mobility_service(ax, mmgraph, 'M4', 'gray')
    # plt.show()
