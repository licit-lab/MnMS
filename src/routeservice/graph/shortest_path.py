from collections import deque, defaultdict
from typing import Callable

from routeservice.graph import OrientedGraph
import numpy as np

def dijkstra(g: OrientedGraph, origin: str, destination: str, cost:str='length') -> deque:
    vertices = set()
    dist = dict()
    prev = dict()

    for v in g.nodes:
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

        for neighbor in g.get_node_neighbors(u):
            if neighbor in vertices:
                alt = dist[u] + g.edges[(u, neighbor)].costs[cost]
                if alt < dist[neighbor]:
                    dist[neighbor] = alt
                    prev[neighbor] = u

    return None

def astar(G: OrientedGraph, origin: str, destination: str, heuristic: Callable, cost:str='length'):
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
            tentative_gscore = gscore[current] + g.edges[(current, neighbor)].costs[cost]
            if tentative_gscore < gscore[neighbor]:
                prev[neighbor] = current
                gscore[neighbor] = tentative_gscore
                fscore[neighbor] = gscore[neighbor] + heuristic(neighbor)
                if neighbor not in discovered_nodes:
                    discovered_nodes.add(neighbor)

    return None

if __name__ == '__main__':
    from routeservice.graph.graph import Node
    from routeservice.graph.render import draw_graph

    import matplotlib.pyplot as plt
    g = OrientedGraph()

    n1 = Node('1', [0, 0])
    n2 = Node('2', [1, 0])
    n3 = Node('3', [1, 1])
    n4 = Node('4', [0, 1])

    g.add_node(n1)
    g.add_node(n2)
    g.add_node(n3)
    g.add_node(n4)

    g.add_link("1", "2", costs={"time": 1})
    g.add_link("2", "3", costs={"time": 1})
    g.add_link("4", "3", costs={"time": 1})
    g.add_link("1", "4", costs={"time": 1})
    g.add_link("1", "3", costs={"time": 10})


    print(dijkstra(g, '1', '3', cost='time'))
    print(astar(g, '1', '3', lambda x: np.linalg.norm(g.nodes[x].pos-g.nodes['3'].pos), cost='length'))

    fig, ax = plt.subplots(figsize=(16, 9))
    draw_graph(ax, g)
    plt.show()