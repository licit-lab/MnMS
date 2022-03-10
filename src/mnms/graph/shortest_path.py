from __future__ import annotations

from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Tuple, List, Literal, Deque, FrozenSet, Union
from functools import partial
from queue import PriorityQueue
from itertools import count

import numpy as np

from mnms.log import create_logger
from mnms.graph.core import TopoGraph, MultiModalGraph, TransitLink
from mnms.graph.search import mobility_nodes_in_radius
from mnms.graph.edition import delete_node_upstream_links, delete_node_downstream_links
from mnms.tools.exceptions import PathNotFound
from mnms.demand.user import User


log = create_logger(__name__)


@dataclass
class Path:
    cost: float | None = None
    mobility_services: FrozenSet[str] = field(default_factory=set)
    nodes: Deque[str] = field(default_factory=deque)


def dijkstra(graph: TopoGraph, origin:str, destination:str, cost: str, available_mobility_services:Union[List[str], None]) -> Path:
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

    vertices = set()
    dist = dict()
    prev = dict()

    for v in graph.nodes:
        dist[v] = float('inf')
        prev[v] = None
        vertices.add(v)

    dist[origin] = 0
    log.debug(f'Dist : {dist}')

    while len(vertices) > 0:
        d = {v:dist[v] for v in vertices}
        u = min(d, key=d.get)
        vertices.remove(u)
        log.debug(f'Prev {prev}')
        log.debug(f"Curr Node {u}")

        if u == destination:
            log.debug(f"Found destination {u}")
            path = Path()
            if prev[u] is not None or u == origin:
                while u is not None:
                    path.nodes.appendleft(u)
                    path.mobility_services.add(graph.nodes[u].mobility_service)
                    u = prev[u]
            path.cost = dist[destination]
            return path

        for neighbor in graph.get_node_neighbors(u):
            log.debug(f"Neighbor Node {neighbor}")
            if neighbor in vertices:

                # Check if next node mobility service is available for the user
                link = graph.links[(u, neighbor)]
                alt = dist[u] + graph.links[(u, neighbor)].costs[cost]
                if isinstance(link, TransitLink):
                    if available_mobility_services is not None:
                        dnode_mobility_service = graph.nodes[link.downstream_node].mobility_service
                        if dnode_mobility_service is not None and dnode_mobility_service not in available_mobility_services:
                            alt = float('inf')

                if alt < dist[neighbor]:
                    dist[neighbor] = alt
                    prev[neighbor] = u

    return Path(float('inf'))


def bidirectional_dijkstra(graph: TopoGraph, origin:str, destination:str, cost: str, available_mobility_services:Union[List[str], None]) -> Path:
    """
    Bidirectional dijkstra algorithm (inspired from NetworkX implementation: https://github.com/networkx/networkx/blob/networkx-2.7.1/networkx/algorithms/shortest_paths/weighted.py#L2229)

    Parameters
    ----------
    graph
    origin
    destination
    cost
    available_mobility_services

    Returns
    -------

    """
    dists = [{}, {}]
    seen = [{origin: 0}, {destination: 0}]

    paths = [{origin: [origin]}, {destination: [destination]}]

    queue = [PriorityQueue(), PriorityQueue()]
    queue[0].put((0, origin))
    queue[1].put((0, destination))

    neighbors = [graph._adjacency, graph._rev_adjacency]

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
            return Path(cost=finaldist,
                        mobility_services=frozenset([graph.nodes[n].mobility_service for n in finalpath]),
                        nodes=deque(finalpath))

        for v in neighbors[dir][u]:
            nodes = [(u, v), (v, u)]
            link = graph.links[nodes[dir]]
            alt = du + link.costs[cost]
            if isinstance(link, TransitLink):
                if available_mobility_services is not None:
                    dnode_mobility_service = graph.nodes[link.downstream_node].mobility_service
                    if dnode_mobility_service is not None and dnode_mobility_service not in available_mobility_services:
                        alt = float('inf')

            if v not in seen[dir] or alt < seen[dir][v]:
                seen[dir][v] = alt
                queue[dir].put((alt, v))
                paths[dir][v] = paths[dir][u] + [v]

                if v in seen[0] and v in seen[1]:
                    totaldist = seen[0][v] + seen[1][v]
                    if finalpath == [] or finaldist > totaldist:
                        finaldist = totaldist
                        revpath = paths[1][v][:]
                        revpath.reverse()
                        finalpath = paths[0][v] + revpath[1:]

    return Path(float('inf'))


def astar(graph: TopoGraph, origin:str, destination:str, cost: str, available_mobility_services:Union[List[str], None], heuristic: Callable[[str, str], float]) -> Path:
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
    discovered_nodes = {origin}
    prev = defaultdict(lambda : None)

    gscore = defaultdict(lambda : float('inf'))
    gscore[origin] = 0

    fscore = defaultdict(lambda : float('inf'))
    fscore[origin] = 0

    while len(discovered_nodes) > 0:
        d = {v: fscore[v] for v in discovered_nodes}
        current = min(d, key=d.get)
        log.info(f"{dict(prev)}, current: {current}")
        if current == destination:
            path = Path()
            if prev[current] is not None or current == origin:
                while current in prev.keys():
                    path.nodes.appendleft(current)
                    path.mobility_services.add(graph.nodes[current].mobility_service)
                    current = prev[current]
                path.nodes.appendleft(current)
                path.mobility_services.add(graph.nodes[current].mobility_service)
            path.cost = fscore[destination]
            return path

        discovered_nodes.remove(current)

        for neighbor in graph.get_node_neighbors(current):

            # Check if next node mobility service is available for the user
            link = graph.links[(current, neighbor)]
            tentative_gscore = gscore[current] + graph.links[(current, neighbor)].costs[cost]
            if isinstance(link, TransitLink):
                if available_mobility_services is not None:
                    dnode_mobility_service = graph.nodes[link.downstream_node].mobility_service
                    if dnode_mobility_service is not None and dnode_mobility_service not in available_mobility_services:
                        tentative_gscore = float('inf')
                        discovered_nodes.add(neighbor)

            if tentative_gscore < gscore[neighbor]:
                prev[neighbor] = current
                gscore[neighbor] = tentative_gscore
                fscore[neighbor] = gscore[neighbor] + heuristic(current, destination)
                if neighbor not in discovered_nodes:
                    discovered_nodes.add(neighbor)

    return Path(float('inf'))


def _euclidian_dist(origin:str, dest:str, mmgraph:MultiModalGraph):
    ref_node_up = mmgraph.mobility_graph.nodes[origin].reference_node
    ref_node_down = mmgraph.mobility_graph.nodes[dest].reference_node

    if ref_node_up is not None and ref_node_down is not None:
        return np.linalg.norm(mmgraph.flow_graph.nodes[ref_node_up].pos - mmgraph.flow_graph.nodes[ref_node_up].pos)
    else:
        return 0


def compute_shortest_path(mmgraph: MultiModalGraph,
                          user: User,
                          cost: str = 'length',
                          algorithm: Literal['dijkstra', 'astar'] = "dijkstra",
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

    if user.available_mobility_service is not None and 'WALK' not in user.available_mobility_service:
        log.warning(f"{user} does not have 'WALK' in its available_mobility_service")

    if algorithm == "dijkstra":
        sh_algo = dijkstra
    elif algorithm == "astar":
        if heuristic is None:
            heuristic = partial(_euclidian_dist, mmgraph=mmgraph)
        sh_algo = partial(astar, heuristic=heuristic)
    else:
        raise NotImplementedError(f"Algorithm '{algorithm}' is not implemented")

    # If user has coordinates as origin/destination
    if isinstance(user.origin, np.ndarray):

        current_radius = radius
        while True:
            service_nodes_origin, dist_origin = mobility_nodes_in_radius(user.origin, mmgraph, current_radius)
            service_nodes_destination, dist_destination = mobility_nodes_in_radius(user.destination, mmgraph,
                                                                                   current_radius)

            if len(service_nodes_destination) == 0 or len(service_nodes_destination) == 0:
                current_radius += growth_rate_radius
            else:
                start_node = f"_{user.id}_START"
                end_node = f"_{user.id}_END"

                mmgraph.mobility_graph.add_node(start_node, None)
                mmgraph.mobility_graph.add_node(end_node, None)

                log.debug(f"Create start artificial links with: {service_nodes_origin}")
                # print(dist_origin[0]/walk_speed)
                for ind, n in enumerate(service_nodes_origin):
                    mmgraph.connect_mobility_service(start_node + '_' + n, start_node, n, 0,
                                                     {'time': dist_origin[ind] / walk_speed,
                                                      'length': dist_origin[ind]})

                log.debug(f"Create end artificial links with: {service_nodes_destination}")
                for ind, n in enumerate(service_nodes_destination):
                    mmgraph.connect_mobility_service(n + '_' + end_node, n, end_node, 0,
                                                     {'time': dist_destination[ind] / walk_speed,
                                                      'length': dist_destination[ind]})

                path = sh_algo(mmgraph.mobility_graph, start_node, end_node, cost, user.available_mobility_service)

                # Clean the graph from artificial nodes

                log.debug(f"Clean graph")

                delete_node_downstream_links(mmgraph.mobility_graph, start_node)
                delete_node_upstream_links(mmgraph.mobility_graph, end_node, service_nodes_destination)
                for n in service_nodes_origin:
                    del mmgraph._connection_services[(start_node, n)]
                for n in service_nodes_destination:
                    del mmgraph._connection_services[(n, end_node)]

                if path.cost != float('inf'):
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

        mmgraph.mobility_graph.add_node(start_node, 'WALK')
        mmgraph.mobility_graph.add_node(end_node, 'WALK')

        log.debug(f"Create start artificial links with: {start_nodes}")
        virtual_cost = {cost: 0}
        virtual_cost.update({'time': 0})
        for n in start_nodes:
            mmgraph.connect_mobility_service(start_node + '_' + n, start_node, n, 0, virtual_cost)

        log.debug(f"Create end artificial links with: {end_nodes}")
        for n in end_nodes:
            mmgraph.connect_mobility_service(n + '_' + end_node, n, end_node, 0, virtual_cost)

        # Compute paths

        log.debug(f"Compute path")

        path = sh_algo(mmgraph.mobility_graph, start_node, end_node, cost, user.available_mobility_service)

        # Clean the graph from artificial nodes

        log.debug(f"Clean graph")

        delete_node_downstream_links(mmgraph.mobility_graph, start_node)
        delete_node_upstream_links(mmgraph.mobility_graph, end_node, end_nodes)
        for n in start_nodes:
            del mmgraph._connection_services[(start_node, n)]
        for n in end_nodes:
            del mmgraph._connection_services[(n, end_node)]

        if path.cost == float('inf'):
            log.warning(f"Path not found for {user}")
            raise PathNotFound(user.origin, user.destination)

        del path.nodes[0]
        del path.nodes[-1]

        return path


def compute_n_best_shortest_path(mmgraph: MultiModalGraph,
                                 user: User,
                                 npath: int,
                                 cost: str='length',
                                 algorithm: Literal['astar', 'dijkstra']='astar',
                                 heuristic: Callable[[str, str], float]=None,
                                 scale_factor: float = 10,
                                 radius:float = 500,
                                 growth_rate_radius: float = 50,
                                 walk_speed: float = 1.4) -> Tuple[List[Path], List[float]]:
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

    if user.available_mobility_service is not None and 'WALK' not in user.available_mobility_service:
        log.warning(f"{user} does not have 'WALK' in its available_mobility_service")

    if algorithm == "dijkstra":
        sh_algo = dijkstra
    elif algorithm == "astar":
        if heuristic is None:
            heuristic = partial(_euclidian_dist, mmgraph=mmgraph)
        sh_algo = partial(astar, heuristic=heuristic)
    else:
        raise NotImplementedError(f"Algorithm '{algorithm}' is not implemented")

    log.debug(f"Compute shortest path User {user.id}")

    if heuristic is None:
        heuristic = partial(_euclidian_dist, mmgraph=mmgraph)

    if isinstance(user.origin, np.ndarray):

        current_radius = radius
        while True:
            service_nodes_origin, dist_origin = mobility_nodes_in_radius(user.origin, mmgraph, current_radius)
            service_nodes_destination, dist_destination = mobility_nodes_in_radius(user.destination, mmgraph,
                                                                                   current_radius)

            if len(service_nodes_origin) == 0 or len(service_nodes_destination) == 0:
                current_radius += growth_rate_radius
                log.info(f"No service found, increase radius of search: {current_radius}")
            else:
                start_node = f"_{user.id}_START"
                end_node = f"_{user.id}_END"

                mmgraph.mobility_graph.add_node(start_node, None)
                mmgraph.mobility_graph.add_node(end_node, None)

                log.debug(f"Create start artificial links with: {service_nodes_origin}")
                # print(dist_origin[0]/walk_speed)
                for ind, n in enumerate(service_nodes_origin):
                    mmgraph.connect_mobility_service(start_node + '_' + n, start_node, n, 0,
                                                     {'time': dist_origin[ind] / walk_speed,
                                                      'length': dist_origin[ind]})

                log.debug(f"Create end artificial links with: {service_nodes_destination}")
                for ind, n in enumerate(service_nodes_destination):
                    mmgraph.connect_mobility_service(n + '_' + end_node, n, end_node, 0,
                                                     {'time': dist_destination[ind] / walk_speed,
                                                      'length': dist_destination[ind]})

                path = sh_algo(mmgraph.mobility_graph, start_node, end_node, cost, user.available_mobility_service)

                if path.cost != float('inf'):
                    counter = 0
                    similar_path = 0
                    while counter < npath:
                        path = sh_algo(mmgraph.mobility_graph, start_node, end_node, cost, user.available_mobility_service)

                        del path.nodes[0]
                        del path.nodes[-1]

                        # Only one possible path
                        if len(path.nodes) == 1:
                            paths.append(path)
                            penalized_costs.append(path.cost)
                            break

                        for ni in range(len(path.nodes) - 1):
                            nj = ni + 1
                            link = topograph_links[(path.nodes[ni], path.nodes[nj])]
                            if (path.nodes[ni], path.nodes[nj]) not in modified_link_cost:
                                modified_link_cost[(path.nodes[ni], path.nodes[nj])] = link.costs[cost]
                            link.costs[cost] = link.costs[cost] * scale_factor

                        if len(paths) > 0:
                            current_path = set(path.nodes)
                            for p in paths:
                                p = set(p.nodes)
                                if p == current_path:
                                    similar_path += 1
                                    break
                            else:
                                counter += 1
                                paths.append(path)
                                penalized_costs.append(path.cost)
                        else:
                            counter += 1
                            paths.append(path)
                            penalized_costs.append(path.cost)

                        if similar_path > 3:
                            log.warning(f'Cant find different paths user {user}')
                            break

                    for lnodes, saved_cost in modified_link_cost.items():
                        mmgraph.mobility_graph.links[lnodes].costs[cost] = saved_cost

                    log.debug(f"Clean graph")

                    delete_node_downstream_links(mmgraph.mobility_graph, start_node)
                    delete_node_upstream_links(mmgraph.mobility_graph, end_node, service_nodes_destination)
                    for n in service_nodes_origin:
                        del mmgraph._connection_services[(start_node, n)]
                    for n in service_nodes_destination:
                        del mmgraph._connection_services[(n, end_node)]
                    break

                else:
                    current_radius += growth_rate_radius
                    log.info(f"No path found, increase radius of search: {current_radius}")

                    log.debug(f"Clean graph")

                    delete_node_downstream_links(mmgraph.mobility_graph, start_node)
                    delete_node_upstream_links(mmgraph.mobility_graph, end_node, service_nodes_destination)
                    for n in service_nodes_origin:
                        del mmgraph._connection_services[(start_node, n)]
                    for n in service_nodes_destination:
                        del mmgraph._connection_services[(n, end_node)]

    else:

        counter = 0
        while counter < npath:
            path = compute_shortest_path(mmgraph, user, cost, algorithm, heuristic)
            for ni in range(len(path.nodes) - 1):
                nj = ni + 1
                link = topograph_links[(path.nodes[ni], path.nodes[nj])]
                if (path.nodes[ni], path.nodes[nj]) not in modified_link_cost:
                    modified_link_cost[(path.nodes[ni], path.nodes[nj])] = link.costs[cost]
                link.costs[cost] = link.costs[cost] * scale_factor

            if len(paths) > 0:
                current_path = set(path.nodes)
                for p in paths:
                    p = set(p.nodes)
                    if p == current_path:
                        break
                else:
                    counter += 1
                    paths.append(path)
                    penalized_costs.append(path.cost)
            else:
                counter += 1
                paths.append(path)
                penalized_costs.append(path.cost)

        for lnodes, saved_cost in modified_link_cost.items():
            mmgraph.mobility_graph.links[lnodes].costs[cost] = saved_cost

    for p in paths:
        p.cost = sum(topograph_links[(p.nodes[n], p.nodes[n+1])].costs[cost] for n in range(len(p.nodes)-1))

    return paths, penalized_costs


if __name__ == "__main__":
    from mnms.mobility_service.personal_car import PersonalCar



    car = PersonalCar('Car')

    car.add_node('C0', '0')
    car.add_node('C1', '1')
    car.add_node('C2', '2')
    car.add_node('C3', '3')
    car.add_node('C4', '0')
    car.add_node('C5', '1')
    car.add_node('C6', '2')
    car.add_node('C7', '3')

    car.add_link('C0_C1', 'C0', 'C1', {"time": 10})
    car.add_link('C1_C2', 'C1', 'C2', {"time": 10})
    car.add_link('C2_C3', 'C2', 'C3', {"time": 10})
    car.add_link('C3_C4', 'C3', 'C4', {"time": 1})
    car.add_link('C0_C7', 'C0', 'C7', {"time": 10})
    car.add_link('C7_C6', 'C7', 'C6', {"time": 10})
    car.add_link('C6_C5', 'C6', 'C5', {"time": 10})
    car.add_link('C5_C4', 'C5', 'C4', {"time": 10})


    print(bidirectional_dijkstra(car._graph, 'C0', 'C4', 'time', None))



