from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Callable, Tuple, List, Literal, Union, Dict
from functools import partial
from queue import PriorityQueue

import numpy as np

from mnms.log import create_logger
from mnms.graph.core import TopoGraph, MultiModalGraph, TransitLink
from mnms.graph.search import mobility_nodes_in_radius
from mnms.graph.edition import delete_node_upstream_links, delete_node_downstream_links
from mnms.tools.exceptions import PathNotFound
from mnms.demand.user import User


log = create_logger(__name__)


class Path(object):
    def __init__(self, cost=None, nodes: List[str] = None):
        self.path_cost: float = cost
        self.layers: List[Tuple[str, slice]] = list()
        self.mobility_services = list()
        self.nodes: List[str] = nodes
        self.service_costs = dict()

    def construct_layers(self, graph):
        layer = graph.nodes[self.nodes[0]].layer
        start = 0
        nodes_number = len(self.nodes)
        for i in range(1, nodes_number-1):
            ilayer = graph.nodes[self.nodes[i]].layer
            if ilayer != layer:
                self.layers.append((layer, slice(start, i, 1)))
                layer = ilayer
                start = i
        self.layers.append((layer, slice(start, nodes_number, 1)))

    def __repr__(self):
        return f"Path(path_cost={self.path_cost}, nodes={self.nodes}, layers={self.layers}, services={self.mobility_services})"

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, deepcopy(v, memo))
        return result

_WEIGHT_COST_TYPE = Union[str, Callable[[Dict[str, float]], float]]


def _weight_computation(cost: _WEIGHT_COST_TYPE):
    if isinstance(cost, str):
        return lambda lcosts:  lcosts[cost]
    elif isinstance(cost, Callable):
        return cost
    else:
        raise TypeError(f"cost argument is either a str or a function, not {type(cost)}")


def dijkstra(graph: TopoGraph,
             origin:str,
             destination:str,
             cost: _WEIGHT_COST_TYPE,
             available_layers:Union[List[str], None]) -> Path:
    """Simple dijkstra shortest path algorithm, it set the `path` attribute of the User with the computed shortest
    path

    Parameters
    ----------
    topograph: TopoGraph
        Topological graph used to compute the shortest path
    user: User
        The user with an origin/destination
    cost: str
        Cost name
    Returns
    -------
    float
        The cost of the path


    """

    cost_func = _weight_computation(cost)

    vertices = set()
    dist = dict()
    prev = dict()

    for v in graph.nodes:
        dist[v] = float('inf')
        prev[v] = None
        vertices.add(v)

    dist[origin] = 0
    prev[origin] = None
    log.debug(f'Dist : {dist}')

    while len(vertices) > 0:
        d = {v:dist[v] for v in vertices}
        u = min(d, key=d.get)
        vertices.remove(u)
        log.debug(f'Prev {prev}')
        log.debug(f"Curr Node {u}")

        if u == destination:
            log.debug(f"Found destination {u}")
            nodes = []
            if prev[u] is not None or u == origin:
                while u is not None:
                    nodes.append(u)
                    u = prev[u]
            nodes.reverse()
            return Path(dist[destination], nodes)

        for neighbor in graph.nodes[u].get_exits(prev[u]):
            log.debug(f"Neighbor Node {neighbor}")
            if neighbor in vertices:

                # Check if next node mobility service is available for the user
                link = graph.links[(u, neighbor)]
                alt = dist[u] + cost_func(graph.links[(u, neighbor)].costs)
                if isinstance(link, TransitLink):
                    if available_layers is not None:
                        dnode_layer = graph.nodes[link.downstream_node].layer
                        if dnode_layer is not None and dnode_layer not in available_layers:
                            alt = float('inf')

                if alt < dist[neighbor]:
                    dist[neighbor] = alt
                    prev[neighbor] = u

    return Path(float('inf'))


def bidirectional_dijkstra(graph: TopoGraph, origin:str, destination:str, cost: _WEIGHT_COST_TYPE, available_layers:Union[List[str], None]) -> Path:
    """
    Bidirectional dijkstra algorithm (inspired from NetworkX implementation: https://github.com/networkx/networkx/blob/networkx-2.7.1/networkx/algorithms/shortest_paths/weighted.py#L2229)

    Parameters
    ----------
    graph
    origin
    destination
    cost
    available_layers

    Returns
    -------

    """
    cost_func = _weight_computation(cost)

    dists = [{}, {}]
    seen = [{origin: 0}, {destination: 0}]

    paths = [{origin: [origin]}, {destination: [destination]}]

    queue = [PriorityQueue(), PriorityQueue()]
    queue[0].put((0, origin))
    queue[1].put((0, destination))

    prev = [{origin: None}, {destination:None}]

    finaldist = float('inf')
    finalpath = []

    dir = 1
    while not queue[0].empty() and not queue[1].empty():
        dir = 1 - dir
        du, u = queue[dir].get()

        if u in dists[dir]:
            continue

        dists[dir][u] = du

        if u in dists[1-dir]:
            path = Path(cost=finaldist,
                        nodes=finalpath)
            return path

        if dir == 0:
            neigh = graph.nodes[u].get_exits(prev[dir][u])
        else:
            neigh = graph.nodes[u].get_entrances(prev[dir][u])

        for v in neigh:
            nodes = [(u, v), (v, u)]
            link = graph.links[nodes[dir]]
            alt = du + cost_func(link.costs)
            if isinstance(link, TransitLink):
                if available_layers is not None:
                    dnode_layer = graph.nodes[link.downstream_node].layer
                    if dnode_layer is not None and dnode_layer not in available_layers:
                        alt = float('inf')

            if v not in seen[dir] or alt < seen[dir][v]:
                seen[dir][v] = alt
                queue[dir].put((alt, v))
                paths[dir][v] = paths[dir][u] + [v]
                prev[dir][v] = u

                if v in seen[0] and v in seen[1]:
                    totaldist = seen[0][v] + seen[1][v]
                    if finalpath == [] or finaldist > totaldist:
                        finaldist = totaldist
                        revpath = paths[1][v][:]
                        revpath.reverse()
                        finalpath = paths[0][v] + revpath[1:]

    return Path(float('inf'))


def astar(graph: TopoGraph, origin:str, destination:str, cost: _WEIGHT_COST_TYPE, available_layers:Union[List[str], None], heuristic: Callable[[str, str], float]) -> Path:
    """A* shortest path algorithm, it set the `path` attribute of the User with the computed shortest
    path

    Parameters
    ----------
    graph: TopoGraph
        Topological graph used to compute the shortest path
    user: User
        The user with an origin/destination
    heuristic: function
        Heuristic to use in the shortest path, take the current node and the destination node and return a float
    cost: str
        Cost name
    Returns
    -------
    float
        The cost of the path

    """

    cost_func = _weight_computation(cost)

    prev = defaultdict(lambda : None)

    gscore = defaultdict(lambda : float('inf'))
    gscore[origin] = 0

    fscore_queue = PriorityQueue()
    fscore_queue.put((0, origin))

    while not fscore_queue.empty():
        _, current = fscore_queue.get()
        log.debug(f"{dict(prev)}, current: {current}")
        if current == destination:
            nodes = []
            if prev[current] is not None or current == origin:
                while current in prev.keys():
                    nodes.append(current)
                    current = prev[current]
                nodes.reverse()
            return Path(gscore[destination], nodes)

        for neighbor in graph.nodes[current].get_exits(prev[current]):

            # Check if next node mobility service is available for the user
            link = graph.links[(current, neighbor)]
            tentative_gscore = gscore[current] + cost_func(link.costs)
            if isinstance(link, TransitLink):
                if available_layers is not None:
                    dnode_layer = graph.nodes[link.downstream_node].layer
                    if dnode_layer is not None and dnode_layer not in available_layers:
                        continue

            if tentative_gscore < gscore[neighbor]:
                prev[neighbor] = current
                gscore[neighbor] = tentative_gscore
                fscore_queue.put((tentative_gscore + heuristic(current, destination), neighbor))

    return Path(float('inf'))


def _euclidian_dist(origin:str, dest:str, mmgraph:MultiModalGraph):
    ref_node_up = mmgraph.mobility_graph.nodes[origin].reference_node
    ref_node_down = mmgraph.mobility_graph.nodes[dest].reference_node

    if ref_node_up is not None and ref_node_down is not None:
        return np.linalg.norm(mmgraph.flow_graph.nodes[ref_node_down].pos - mmgraph.flow_graph.nodes[ref_node_up].pos)
    else:
        return 0


def compute_shortest_path(mmgraph: MultiModalGraph,
                          user: User,
                          cost: _WEIGHT_COST_TYPE = lambda cost: cost['travel_time'] + cost['waiting_time'],
                          algorithm: Literal['dijkstra', 'bidirectional_dijkstra', 'astar'] = "astar",
                          heuristic: Callable[[str, str], float] = None,
                          radius: float = 500,
                          growth_rate_radius: float = 10,
                          walk_speed: float = 1.4) -> Path:
    """Compute shortest path from a User origin/destination and a multimodal graph

    Parameters
    ----------
    mmgraph: MultiModalGraph
        The multimodal graph to use for the shortest path algorithm
    user: User
        The user with an origin/destination
    cost: str
        The cost name
    algorithm: str
        The algorithm to use for the shortest path computation
    heuristic: function
        The heuristic function to use if astar is chosen as algorithm
    radius: float
        The radius of mobility service search around the User if its origin/destination are coordinates
    growth_rate_radius: float
        The radius growth if no path is found from origin to destination if User origin/destination are coordinates
    walk_speed: float
        The walk speed in m/s

    Returns
    -------
    float
        The cost of the path

    """

    if user.available_mobility_service is not None:
        user_accessible_layers = {mmgraph.mapping_layer_services[mservice].id for mservice in user.available_mobility_service}
        user_accessible_layers.add('WALK')
    else:
        user_accessible_layers = None

    if algorithm == "dijkstra":
        sh_algo = dijkstra
    elif algorithm == "bidirectional_dijkstra":
        sh_algo = bidirectional_dijkstra
    elif algorithm == "astar":
        if heuristic is None:
            heuristic = partial(_euclidian_dist, mmgraph=mmgraph)
        sh_algo = partial(astar, heuristic=heuristic)
    else:
        raise NotImplementedError(f"Algorithm '{algorithm}' is not implemented")

    # If user has coordinates as origin/destination
    if isinstance(user.origin, np.ndarray) and isinstance(user.destination, np.ndarray):

        current_radius = radius
        while True:
            service_nodes_origin, dist_origin = mobility_nodes_in_radius(user.origin,
                                                                         mmgraph,
                                                                         current_radius,
                                                                         user.available_mobility_service)
            service_nodes_destination, dist_destination = mobility_nodes_in_radius(user.destination,
                                                                                   mmgraph,
                                                                                   current_radius,
                                                                                   user.available_mobility_service)

            if len(service_nodes_origin) == 0 or len(service_nodes_destination) == 0:
                current_radius += growth_rate_radius
            else:
                start_node = f"_{user.id}_START"
                end_node = f"_{user.id}_END"

                mmgraph.mobility_graph.create_node(start_node, None, None)
                mmgraph.mobility_graph.create_node(end_node, None, None)

                log.debug(f"Create start artificial links with: {service_nodes_origin}")
                # print(dist_origin[0]/walk_speed)
                for ind, n in enumerate(service_nodes_origin):
                    mmgraph.connect_layers(start_node + '_' + n, start_node, n, 0,
                                           {'travel_time': dist_origin[ind] / walk_speed,
                                            'length': dist_origin[ind]})

                log.debug(f"Create end artificial links with: {service_nodes_destination}")
                for ind, n in enumerate(service_nodes_destination):
                    mmgraph.connect_layers(n + '_' + end_node, n, end_node, 0,
                                           {'travel_time': dist_destination[ind] / walk_speed,
                                            'length': dist_destination[ind]})

                # user.available_mobility_service -> user_accessible_layers
                path = sh_algo(mmgraph.mobility_graph, start_node, end_node, cost, user_accessible_layers)

                # Clean the graph from artificial nodes

                log.debug(f"Clean graph")

                delete_node_downstream_links(mmgraph.mobility_graph, start_node)
                delete_node_upstream_links(mmgraph.mobility_graph, end_node, service_nodes_destination)
                for n in service_nodes_origin:
                    del mmgraph.connection_layers[(start_node, n)]
                for n in service_nodes_destination:
                    del mmgraph.connection_layers[(n, end_node)]

                if path.path_cost != float('inf'):
                    break

                current_radius += growth_rate_radius

        del path.nodes[0]
        del path.nodes[-1]

        return path

    else:

        start_nodes = [n for n in mmgraph.mobility_graph.get_node_references(user.origin)]
        end_nodes = [n for n in mmgraph.mobility_graph.get_node_references(user.destination)]

        if len(start_nodes) == 0:
            log.warning(f"There is no mobility service connected to origin node {user.origin}")
            raise PathNotFound(user.origin, user.destination)

        if len(end_nodes) == 0:
            log.warning(f"There is no mobility service connected to destination node {user.destination}")
            raise PathNotFound(user.origin, user.destination)

        start_node = f"START_{user.origin}_{user.destination}"
        end_node = f"END_{user.origin}_{user.destination}"
        log.debug(f"Create artitificial nodes: {start_node}, {end_node}")

        mmgraph.mobility_graph.create_node(start_node, 'WALK', None)
        mmgraph.mobility_graph.create_node(end_node, 'WALK', None)

        log.debug(f"Create start artificial links with: {start_nodes}")
        virtual_cost = {cost: 0} if isinstance(cost, str) else {}
        virtual_cost.update({'time': 0})
        for n in start_nodes:
            mmgraph.connect_layers(start_node + '_' + n, start_node, n, 0, virtual_cost)

        log.debug(f"Create end artificial links with: {end_nodes}")
        for n in end_nodes:
            mmgraph.connect_layers(n + '_' + end_node, n, end_node, 0, virtual_cost)

        # Compute paths

        log.debug(f"Compute path")

        path = sh_algo(mmgraph.mobility_graph, start_node, end_node, cost, user_accessible_layers)

        # Clean the graph from artificial nodes

        log.debug(f"Clean graph")

        delete_node_downstream_links(mmgraph.mobility_graph, start_node)
        delete_node_upstream_links(mmgraph.mobility_graph, end_node, end_nodes)
        for n in start_nodes:
            del mmgraph.connection_layers[(start_node, n)]
        for n in end_nodes:
            del mmgraph.connection_layers[(n, end_node)]

        if path.path_cost == float('inf'):
            log.warning(f"Path not found for {user}")
            raise PathNotFound(user.origin, user.destination)

        del path.nodes[0]
        del path.nodes[-1]

        return path


def compute_n_best_shortest_path(mmgraph: MultiModalGraph,
                                 user: User,
                                 npath: int,
                                 cost: _WEIGHT_COST_TYPE = 'length',
                                 algorithm: Literal['dijkstra', 'bidirectional_dijkstra', 'astar'] = 'astar',
                                 heuristic: Callable[[str, str], float]=None,
                                 scale_factor: float = 10,
                                 radius:float = 500,
                                 growth_rate_radius: float = 50,
                                 walk_speed: float = 1.4,
                                 max_consecutive_run: int = 10) -> Tuple[List[Path], List[float]]:
    """Compute n best shortest path by increasing the costs of the links previously found as shortest path.

    Parameters
    ----------
    mmgraph: MultiModalGraph
        The multimodal graph to use for the shortest path algorithm
    user: User
        The user with an origin/destination
    npath: int
        Number of shortest path to compute
    cost: str
        The cost name
    algorithm: str
        The algorithm to use for the shortest path computation
    heuristic: function
        The heuristic function to use if astar is chosen as algorithm
    scale_factor: int
        The factor to use for increasing the link costs
    radius: float
        The radius of mobility service search around the User if its origin/destination are coordinates
    growth_rate_radius: float
        The radius growth if no path is found from origin to destination if User origin/destination are coordinates
    walk_speed: float
        The walk speed in m/s
    max_consecutive_run: int
        Number of consecutive shortest path computation, if the number of consecutive shortest path is beyond returns the
        already computed shortest paths

    Returns
    -------
    list(list(str)), list(float), list(float)
        Returns the computed paths, the real costs of those paths and the penalized costs of the paths

    """

    assert npath >= 1
    modified_link_cost = dict()
    paths = []
    penalized_costs = []
    topograph_links = mmgraph.mobility_graph.links

    if user.available_mobility_service is not None:
        user_accessible_layers = {mmgraph.mapping_layer_services[mservice].id for mservice in user.available_mobility_service}
        user_accessible_layers.add('WALK')
    else:
        user_accessible_layers = None

    if algorithm == "dijkstra":
        sh_algo = dijkstra
    elif algorithm == "bidirectional_dijkstra":
        sh_algo = bidirectional_dijkstra
    elif algorithm == "astar":
        if heuristic is None:
            heuristic = partial(_euclidian_dist, mmgraph=mmgraph)
        sh_algo = partial(astar, heuristic=heuristic)
    else:
        raise NotImplementedError(f"Algorithm '{algorithm}' is not implemented")

    log.debug(f"Compute shortest path User {user.id}")

    if isinstance(user.origin, np.ndarray):

        current_radius = radius
        while True:
            service_nodes_origin, dist_origin = mobility_nodes_in_radius(user.origin,
                                                                         mmgraph,
                                                                         current_radius,
                                                                         user.available_mobility_service)
            service_nodes_destination, dist_destination = mobility_nodes_in_radius(user.destination,
                                                                                   mmgraph,
                                                                                   current_radius,
                                                                                   user.available_mobility_service)

            if len(service_nodes_origin) == 0 or len(service_nodes_destination) == 0:
                current_radius += growth_rate_radius
                log.info(f"No service found, increase radius of search: {current_radius}")
            else:
                start_node = f"_{user.id}_START"
                end_node = f"_{user.id}_END"

                mmgraph.mobility_graph.create_node(start_node, None, None)
                mmgraph.mobility_graph.create_node(end_node, None, None)

                log.debug(f"Create start artificial links with: {service_nodes_origin}")
                # print(dist_origin[0]/walk_speed)
                for ind, n in enumerate(service_nodes_origin):
                    mmgraph.connect_layers(start_node + '_' + n, start_node, n, 0,
                                           {'travel_time': dist_origin[ind] / walk_speed,
                                            'length': dist_origin[ind]})

                log.debug(f"Create end artificial links with: {service_nodes_destination}")
                for ind, n in enumerate(service_nodes_destination):
                    mmgraph.connect_layers(n + '_' + end_node, n, end_node, 0,
                                           {'travel_time': dist_destination[ind] / walk_speed,
                                            'length': dist_destination[ind]})

                path = sh_algo(mmgraph.mobility_graph, start_node, end_node, cost, user_accessible_layers)

                if path.path_cost != float('inf'):
                    computed_paths = 0
                    consecutive_run_number = 0
                    while computed_paths < npath:
                        if consecutive_run_number > max_consecutive_run:
                            log.warning(
                                f'Reach max number of shortest path computation ({max_consecutive_run}), returning the already computed paths')
                            break
                        path = sh_algo(mmgraph.mobility_graph, start_node, end_node, cost, user_accessible_layers)

                        del path.nodes[0]
                        del path.nodes[-1]

                        # Only one possible path
                        if len(path.nodes) == 1:
                            paths.append(path)
                            penalized_costs.append(path.path_cost)
                            break

                        for ni in range(len(path.nodes) - 1):
                            nj = ni + 1
                            link = topograph_links[(path.nodes[ni], path.nodes[nj])]
                            if (path.nodes[ni], path.nodes[nj]) not in modified_link_cost:
                                modified_link_cost[(path.nodes[ni], path.nodes[nj])] = deepcopy(link.costs)
                            link.costs.update({k: v * scale_factor for k, v in link.costs.items()})

                        if len(paths) > 0:
                            current_path = set(path.nodes)
                            for p in paths:
                                p = set(p.nodes)
                                if p == current_path:
                                    consecutive_run_number += 1
                                    break
                            else:
                                computed_paths += 1
                                paths.append(path)
                                penalized_costs.append(path.path_cost)
                        else:
                            computed_paths += 1
                            paths.append(path)
                            penalized_costs.append(path.path_cost)

                    for lnodes, saved_cost in modified_link_cost.items():
                        mmgraph.mobility_graph.links[lnodes].costs = saved_cost

                    log.debug(f"Clean graph")

                    delete_node_downstream_links(mmgraph.mobility_graph, start_node)
                    delete_node_upstream_links(mmgraph.mobility_graph, end_node, service_nodes_destination)
                    for n in service_nodes_origin:
                        del mmgraph.connection_layers[(start_node, n)]
                    for n in service_nodes_destination:
                        del mmgraph.connection_layers[(n, end_node)]
                    break

                else:
                    current_radius += growth_rate_radius
                    log.info(f"No path found, increase radius of search: {current_radius}")

                    log.debug(f"Clean graph")

                    delete_node_downstream_links(mmgraph.mobility_graph, start_node)
                    delete_node_upstream_links(mmgraph.mobility_graph, end_node, service_nodes_destination)
                    for n in service_nodes_origin:
                        del mmgraph.connection_layers[(start_node, n)]
                    for n in service_nodes_destination:
                        del mmgraph.connection_layers[(n, end_node)]

    else:

        computed_paths = 0
        consecutive_run_number = 0
        while computed_paths < npath:
            if consecutive_run_number > max_consecutive_run:
                log.warning(f'Reach max number of shortest path computation ({max_consecutive_run}), returning the already computed paths')
                break
            path = compute_shortest_path(mmgraph, user, cost, algorithm, heuristic)
            for ni in range(len(path.nodes) - 1):
                nj = ni + 1
                link = topograph_links[(path.nodes[ni], path.nodes[nj])]
                if (path.nodes[ni], path.nodes[nj]) not in modified_link_cost:
                    modified_link_cost[(path.nodes[ni], path.nodes[nj])] = deepcopy(link.costs)
                link.costs.update({k: v * scale_factor for k, v in link.costs.items()})

            if len(paths) > 0:
                current_path = set(path.nodes)
                for p in paths:
                    p = set(p.nodes)
                    if p == current_path:
                        consecutive_run_number += 1
                        break
                else:
                    consecutive_run_number = 0
                    computed_paths += 1
                    paths.append(path)
                    penalized_costs.append(path.path_cost)
            else:
                consecutive_run_number = 0
                computed_paths += 1
                paths.append(path)
                penalized_costs.append(path.path_cost)

        for lnodes, saved_cost in modified_link_cost.items():
            mmgraph.mobility_graph.links[lnodes].costs = saved_cost

    for p in paths:
        p.cost = sum(topograph_links[(p.nodes[n], p.nodes[n+1])].costs[cost] for n in range(len(p.nodes)-1))

    return paths, penalized_costs
