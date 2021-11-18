from collections import deque, defaultdict
from typing import Callable

import numpy as np

def dijkstra(G, origin: str, destination: str, cost:str='length') -> deque:
    vertices = set()
    dist = dict()
    prev = dict()

    for v in G.nodes:
        dist[v] = float('inf')
        prev[v] = None
        vertices.add(v)

    dist[origin] = 0

    while len(vertices) > 0:
        d = {v:dist[v] for v in vertices}
        u = min(d, key=d.get)
        vertices.remove(u)

        if u == destination:
            path = deque()
            if prev[u] is not None or u == origin:
                while u is not None:
                    path.appendleft(u)
                    u = prev[u]

            return dist[destination], path

        for neighbor in G.get_node_neighbors(u):
            if neighbor in vertices:
                alt = dist[u] + G.links[(u, neighbor)].costs[cost]
                if alt < dist[neighbor]:
                    dist[neighbor] = alt
                    prev[neighbor] = u

    return float('inf'), None



def astar(G, origin: str, destination: str, heuristic: Callable, cost:str='length'):
    discovered_nodes = set([origin])
    prev = dict()

    gscore = defaultdict(lambda : float('inf'))
    gscore[origin] = 0

    fscore = defaultdict(lambda : float('inf'))
    fscore[origin] = heuristic(origin)

    while len(discovered_nodes) > 0:
        d = {v: fscore[v] for v in discovered_nodes}
        current = min(d, key=d.get)

        if current == destination:
            path = deque()
            if prev[current] is not None or current == origin:
                while current in prev.keys():
                    path.appendleft(current)
                    current = prev[current]
                path.appendleft(current)
            return fscore[destination], path

        discovered_nodes.remove(current)

        for neighbor in G.get_node_neighbors(current):
            tentative_gscore = gscore[current] + G.links[(current, neighbor)].costs[cost]
            if tentative_gscore < gscore[neighbor]:
                prev[neighbor] = current
                gscore[neighbor] = tentative_gscore
                fscore[neighbor] = gscore[neighbor] + heuristic(neighbor)
                if neighbor not in discovered_nodes:
                    discovered_nodes.add(neighbor)

    return float('inf'), None

if __name__ == '__main__':
    from routeservice.graph.structure import MultiModalGraph

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
    uber_service = mmgraph.add_mobility_service('Uber')

    bus_service.add_node('0')
    bus_service.add_node('1')
    bus_service.add_node('2')

    bus_service.add_link('BUS_0_1', '0', '1', {'time': 5.5}, reference_links=['0_1'])
    bus_service.add_link('BUS_1_2', '1', '2', {'time': 5.5}, reference_links=['1_2'])
    bus_service.add_link('BUS_0_2', '0', '2', {'time': 2.3}, reference_links=[])

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


    uber_service.add_node('0')
    uber_service.add_node('1')

    uber_service.add_link('UBER_0_1', '0', '1', {'time': 5.5}, reference_links=['0_1'])

    mmgraph.connect_mobility_service('Bus', 'Car', '0', {'time': 2})
    mmgraph.connect_mobility_service('Bus', 'Car', '1', {'time': 2})
    mmgraph.connect_mobility_service('Bus', 'Car', '2', {'time': 2});

    mmgraph.connect_mobility_service('Bus', 'Uber', '0', {'time': 4})
    mmgraph.connect_mobility_service('Bus', 'Uber', '1', {'time': 4})

    print(dijkstra(mmgraph.mobility_graph, 'Bus_0', 'Car_2', cost="time"))

