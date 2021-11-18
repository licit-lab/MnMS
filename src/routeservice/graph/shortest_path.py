from collections import deque, defaultdict
from typing import Callable

from routeservice.graph.graph import TopoGraph
import numpy as np

def dijkstra(G: TopoGraph, origin: str, destination: str, cost:str='length') -> deque:
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

            return path

        for neighbor in G.get_node_neighbors(u):
            if neighbor in vertices:
                alt = dist[u] + G.links[(u, neighbor)].costs[cost]
                if alt < dist[neighbor]:
                    dist[neighbor] = alt
                    prev[neighbor] = u

    return None

def dijkstra_multi_edge(G: TopoGraph, origin: str, destination: str, cost:str='length') -> deque:
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
                path.appendleft(u)
                u = prev[u]
                while u is not None:
                    link = u[1]
                    u = u[0]
                    path.appendleft(link)
                    path.appendleft(u)
                    u = prev[u]
            return path

        for neighbor in G.get_node_neighbors(u):
            if neighbor in vertices:
                all_costs = []
                for edg in G.links[(u, neighbor)]:
                    all_costs.append(dist[u] + edg.costs[cost])
                min_cost_index = np.argmin(all_costs)
                alt = all_costs[min_cost_index]
                if alt < dist[neighbor]:
                    dist[neighbor] = alt
                    prev[neighbor] = [u, G.links[(u, neighbor)][min_cost_index].id]

    return None



def astar(G: TopoGraph, origin: str, destination: str, heuristic: Callable, cost:str='length'):
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
            return path

        discovered_nodes.remove(current)

        for neighbor in G.get_node_neighbors(current):
            tentative_gscore = gscore[current] + G.links[(current, neighbor)].costs[cost]
            if tentative_gscore < gscore[neighbor]:
                prev[neighbor] = current
                gscore[neighbor] = tentative_gscore
                fscore[neighbor] = gscore[neighbor] + heuristic(neighbor)
                if neighbor not in discovered_nodes:
                    discovered_nodes.add(neighbor)

    return None

def astar_multi_edge(G: TopoGraph, origin: str, destination: str, heuristic: Callable, cost:str='length'):
    discovered_nodes = set([origin])
    prev = defaultdict(lambda: None)

    gscore = defaultdict(lambda : float('inf'))
    gscore[origin] = 0

    fscore = defaultdict(lambda : float('inf'))
    fscore[origin] = heuristic(origin)

    while len(discovered_nodes) > 0:
        d = {v: fscore[v] for v in discovered_nodes}
        current = min(d, key=d.get)

        if current == destination:
            path = deque()
            path.appendleft(current)
            if prev[current] is not None or current == origin:
                current = prev[current]
                while current[0] in prev.keys():
                    link = current[1]
                    current = current[0]
                    path.appendleft(link)
                    path.appendleft(current)
                    current = prev[current]
            path.appendleft(current[1])
            path.appendleft(current[0])
            return path

        discovered_nodes.remove(current)

        for neighbor in G.get_node_neighbors(current):
            all_costs = []
            for edg in G.links[(current, neighbor)]:
                all_costs.append(gscore[current] + edg.costs[cost])
            min_cost_index = np.argmin(all_costs)
            tentative_gscore = all_costs[min_cost_index]
            if tentative_gscore < gscore[neighbor]:
                prev[neighbor] = [current, G.links[(current, neighbor)][min_cost_index].id]
                gscore[neighbor] = tentative_gscore
                fscore[neighbor] = gscore[neighbor] + heuristic(neighbor)
                if neighbor not in discovered_nodes:
                    discovered_nodes.add(neighbor)

    return None

if __name__ == '__main__':
    from routeservice.graph.graph import MultiModalGraph

    mmgraph = MultiModalGraph()

    mmgraph.flow_graph.add_node('0', [0, 0])
    mmgraph.flow_graph.add_node('1', [1, 0])


    mmgraph.flow_graph.add_link('0_1', '0', '1')
    mmgraph.flow_graph.add_link('1_0', '1', '0')

    bus_service = mmgraph.add_mobility_service('Bus')
    car_service = mmgraph.add_mobility_service('Car')

    bus_service.add_node('0')
    bus_service.add_node('1')

    bus_service.add_link('BUS_0_1', '0', '1', {'time': 10.4}, reference_links=['0_1'])

    car_service.add_node('0')
    car_service.add_node('1')

    car_service.add_link('CAR_0_1', '0', '1', {'time': 15.1}, reference_links=['0_1'])


    # print(astar(mmgraph.mobility_graph, '0', '2', lambda x: 0, cost='time'))
    print(dijkstra_multi_edge(mmgraph.mobility_graph, '0', '1', cost='time'))
    print(astar_multi_edge(mmgraph.mobility_graph, '0', '1', lambda x:0, cost='time'))

