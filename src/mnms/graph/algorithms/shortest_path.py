from collections import deque, defaultdict
from typing import Callable, Tuple, Deque, List
from functools import partial

import numpy as np

from mnms.log import rootlogger
from mnms.graph.core import TopoGraph, MultiModalGraph, TransitLink
from mnms.tools.exceptions import PathNotFound
from mnms.demand.user import User


# TODO: Adapt dijkstra with User class and available mobility service
def dijkstra(G: TopoGraph, user:User, cost:str) -> Tuple[float, Deque[str]]:
    origin = user.origin
    destination = user.destination
    vertices = set()
    dist = dict()
    prev = dict()

    for v in G.nodes:
        dist[v] = float('inf')
        prev[v] = None
        vertices.add(v)

    dist[origin] = 0
    rootlogger.debug(f'Dist : {dist}')

    while len(vertices) > 0:
        d = {v:dist[v] for v in vertices}
        u = min(d, key=d.get)
        vertices.remove(u)
        rootlogger.debug(f'Prev {prev}')
        rootlogger.debug(f"Curr Node {u}")

        if u == destination:
            rootlogger.debug(f"Found destination {u}")
            path = deque()
            if prev[u] is not None or u == origin:
                while u is not None:
                    path.appendleft(u)
                    u = prev[u]
            user.path = path
            return dist[destination]

        for neighbor in G.get_node_neighbors(u):
            rootlogger.debug(f"Neighbor Node {neighbor}")
            if neighbor in vertices:
                alt = dist[u] + G.links[(u, neighbor)].costs[cost]
                if alt < dist[neighbor]:
                    dist[neighbor] = alt
                    prev[neighbor] = u


def astar(G: TopoGraph, user:User, heuristic: Callable[[str, str], float], cost:str) -> float:
    origin = user.origin
    destination = user.destination
    discovered_nodes = {origin}
    prev = dict()

    gscore = defaultdict(lambda : float('inf'))
    gscore[origin] = 0

    fscore = defaultdict(lambda : float('inf'))
    fscore[origin] = 0

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
            user.path = list(path)
            return fscore[destination]

        discovered_nodes.remove(current)

        for neighbor in G.get_node_neighbors(current):

            # Check if next node mobility service is available for the user
            link = G.links[(current, neighbor)]
            if isinstance(link, TransitLink):
                if user.available_mobility_service is not None:
                    if G.nodes[link.downstream_node].mobility_service not in user.available_mobility_service:
                        tentative_gscore = float('inf')
                    else:
                        tentative_gscore = gscore[current] + G.links[(current, neighbor)].costs[cost]
                else:
                    tentative_gscore = gscore[current] + G.links[(current, neighbor)].costs[cost]
            else:
                tentative_gscore = gscore[current] + G.links[(current, neighbor)].costs[cost]

            if tentative_gscore < gscore[neighbor]:
                prev[neighbor] = current
                gscore[neighbor] = tentative_gscore
                fscore[neighbor] = gscore[neighbor] + heuristic(current, destination)
                if neighbor not in discovered_nodes:
                    discovered_nodes.add(neighbor)

    return float('inf')


def _euclidian_dist(origin, dest, mmgraph):
    ref_node_up = mmgraph.mobility_graph.nodes[origin].reference_node
    ref_node_down = mmgraph.mobility_graph.nodes[dest].reference_node

    if ref_node_up is not None and ref_node_down is not None:
        return np.linalg.norm(mmgraph.flow_graph.nodes[ref_node_up].pos - mmgraph.flow_graph.nodes[ref_node_up].pos)
    else:
        return 0


def _create_virtual_nodes(mmgraph, user, cost_name):
    origin = user.origin
    destination = user.destination
    start_nodes = [n for n in mmgraph.mobility_graph.get_node_references(origin)]
    end_nodes = [n for n in mmgraph.mobility_graph.get_node_references(destination)]

    if len(start_nodes) == 0:
        rootlogger.error(f"There is no mobility service connected to origin node {origin}")
        return float('inf')

    if len(end_nodes) == 0:
        rootlogger.error(f"There is no mobility service connected to destination node {destination}")
        return float('inf')


    start_node = f"START_{origin}_{destination}"
    end_node = f"END_{origin}_{destination}"
    rootlogger.debug(f"Create artitificial nodes: {start_node}, {end_node}")

    mmgraph.mobility_graph.add_node(start_node, 'NULL')
    mmgraph.mobility_graph.add_node(end_node, 'NULL')

    rootlogger.debug(f"Create start artitificial links with: {start_nodes}")
    virtual_cost = {cost_name: 0}
    virtual_cost.update({'time': 0})
    for n in start_nodes:
        mmgraph.connect_mobility_service(start_node + '_' + n, start_node, n, virtual_cost)

    rootlogger.debug(f"Create end artitificial links with: {end_nodes}")
    for n in end_nodes:
        mmgraph.connect_mobility_service(n + '_' + end_node, n, end_node, virtual_cost)

    user.origin = start_node
    user.destination = end_node


def _delete_virtual_nodes(mmgraph, user):
    rootlogger.debug(f"Clean graph")
    start_node = user.origin
    end_node = user.destination

    splitted_start_node = start_node.split('_')
    origin = splitted_start_node[1]
    destination = splitted_start_node[2]
    start_nodes = (n for n in mmgraph.mobility_graph.get_node_references(origin))
    end_nodes = (n for n in mmgraph.mobility_graph.get_node_references(destination))
    del mmgraph.mobility_graph.nodes[start_node]
    del mmgraph.mobility_graph.nodes[end_node]
    del mmgraph.mobility_graph._adjacency[start_node]

    for n in start_nodes:
        del mmgraph.mobility_graph.links[(start_node, n)]
        del mmgraph.mobility_graph._map_lid_nodes[start_node + '_' + n]
        del mmgraph._connection_services[(start_node, n)]

    for n in end_nodes:
        del mmgraph.mobility_graph.links[(n, end_node)]
        del mmgraph.mobility_graph._map_lid_nodes[n + '_' + end_node]
        mmgraph.mobility_graph._adjacency[n].remove(end_node)
        del mmgraph._connection_services[(n, end_node)]


# TODO: make use of algorithm arg with either dijkstra or astar
def compute_shortest_path(mmgraph: MultiModalGraph, user:User, cost:str='length', algorithm:str="dijkstra", heuristic=None) -> float:
    # Create artificial nodes
    origin = user.origin
    destination = user.destination

    _create_virtual_nodes(mmgraph, user, cost)

    # Compute paths

    rootlogger.debug(f"Compute path")

    if algorithm == "dijkstra":
        cost = dijkstra(mmgraph.mobility_graph, user, cost)
    elif algorithm == "astar":
        if heuristic is None:
            heuristic = partial(_euclidian_dist, mmgraph=mmgraph)
        cost = astar(mmgraph.mobility_graph, user, heuristic, cost)
    else:
        user.origin = origin
        user.destination = destination
        raise NotImplementedError(f"Algorithm '{algorithm}' is not implemented")

    # Clean the graph from artificial nodes

    rootlogger.debug(f"Clean graph")
    _delete_virtual_nodes(mmgraph, user)
    user.origin = origin
    user.destination = destination

    if cost == float('inf'):
        raise PathNotFound(origin, destination)

    del user.path[0]
    del user.path[-1]

    return cost


def batch_compute_shortest_path(mmgraph, origins, destinations, algorithm='astar', heuristic=None):
    pass


def compute_n_best_shortest_path(mmgraph, user, nrun, cost:str='length', algorithm='astar', heuristic=None, scale_factor=10) -> List[List[float]]:
    assert nrun >= 1
    modified_link_cost = dict()
    paths = []
    costs = []

    counter = 0
    while counter < nrun:
        c = compute_shortest_path(mmgraph, user, cost, algorithm, heuristic)
        for ni in range(len(user.path) - 1):
            nj = ni + 1
            link = mmgraph.mobility_graph.links[(user.path[ni], user.path[nj])]
            if (user.path[ni], user.path[nj]) not in modified_link_cost:
                modified_link_cost[(user.path[ni], user.path[nj])] = link.costs[cost]
            link.costs[cost] = link.costs[cost] * 10

        if len(paths) > 0:
            current_path = set(user.path)
            for p in paths:
                p = set(p)
                if p == current_path:
                    break
            else:
                counter += 1
                paths.append(user.path[:])
                costs.append(c)
        else:
            counter += 1
            paths.append(user.path[:])
            costs.append(c)

    for lnodes, saved_cost in modified_link_cost.items():
        mmgraph.mobility_graph.links[lnodes].costs[cost] = saved_cost

    user.path = None

    return paths, costs





