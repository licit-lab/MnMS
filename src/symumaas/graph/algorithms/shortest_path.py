from collections import deque, defaultdict
from typing import Callable

import numpy as np

def dijkstra(G, origin: str, destination: str, cost:str) -> deque:
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



def astar(G, origin: str, destination: str, heuristic: Callable, cost:str):
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