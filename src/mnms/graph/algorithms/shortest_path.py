from collections import deque, defaultdict
from typing import Callable, Tuple, Deque

from mnms.log import logger
from mnms.graph.core import TopoGraph, MultiModalGraph

import numpy as np

def dijkstra(G: TopoGraph, origin: str, destination: str, cost:str) -> Tuple[float, Deque[str]]:
    vertices = set()
    dist = dict()
    prev = dict()

    for v in G.nodes:
        dist[v] = float('inf')
        prev[v] = None
        vertices.add(v)

    dist[origin] = 0
    logger.debug(f'Dist : {dist}')

    while len(vertices) > 0:
        d = {v:dist[v] for v in vertices}
        u = min(d, key=d.get)
        vertices.remove(u)
        logger.debug(f'Prev {prev}')
        logger.debug(f"Curr Node {u}")

        if u == destination:
            logger.debug(f"Found destination {u}")
            path = deque()
            if prev[u] is not None or u == origin:
                while u is not None:
                    path.appendleft(u)
                    u = prev[u]
            return dist[destination], path

        for neighbor in G.get_node_neighbors(u):
            logger.debug(f"Neighbor Node {neighbor}")
            if neighbor in vertices:
                alt = dist[u] + G.links[(u, neighbor)].costs[cost]
                if alt < dist[neighbor]:
                    dist[neighbor] = alt
                    prev[neighbor] = u

    return float('inf'), deque()



def astar(G: TopoGraph, origin: str, destination: str, heuristic: Callable, cost:str) -> Tuple[float, Deque[str]]:
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

    return float('inf'), deque()



# TODO: make use of algorithm arg with either dijkstra or astar
def compute_shortest_path(mmgraph: MultiModalGraph, origin:str, destination:str, cost:str='length', algorithm:str="dijkstra") -> Tuple[float, Tuple[str]]:
    # Create artificial nodes

    start_nodes = [n for n in mmgraph.mobility_graph.get_node_references(origin)]
    end_nodes = [n for n in mmgraph.mobility_graph.get_node_references(destination)]

    if len(start_nodes) == 0:
        logger.error(f"There is no mobility service connected to origin node {origin}")
        return float('inf'), deque()

    if len(end_nodes) == 0:
        logger.error(f"There is no mobility service connected to destination node {destination}")
        return float('inf'), deque()


    start_node = f"START_{origin}_{destination}"
    end_node = f"END_{origin}_{destination}"
    logger.debug(f"Create artitificial nodes: {start_node}, {end_node}")

    mmgraph.mobility_graph.add_node(start_node, 'NULL')
    mmgraph.mobility_graph.add_node(end_node, 'NULL')

    logger.debug(f"Create start artitificial links with: {start_nodes}")
    for n in start_nodes:
        mmgraph.mobility_graph.add_link(start_node + '_' + n, start_node, n, {cost: 0})

    logger.debug(f"Create end artitificial links with: {end_nodes}")
    for n in end_nodes:
        mmgraph.mobility_graph.add_link(n + '_' + end_node, n, end_node, {cost: 0})

    # Compute paths

    logger.debug(f"Compute path")
    cost, path = dijkstra(mmgraph.mobility_graph, start_node, end_node, cost)

    # Clean the graph from artificial nodes

    logger.debug(f"Clean graph")
    del mmgraph.mobility_graph.nodes[start_node]
    del mmgraph.mobility_graph.nodes[end_node]
    del mmgraph.mobility_graph._adjacency[start_node]

    for n in start_nodes:
        del mmgraph.mobility_graph.links[(start_node, n)]

    for n in end_nodes:
        del mmgraph.mobility_graph.links[(n, end_node)]
        mmgraph.mobility_graph._adjacency[n].remove(end_node)

    del path[0]
    del path[-1]

    return cost, tuple(path)
