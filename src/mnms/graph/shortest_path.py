from collections import deque, defaultdict
from typing import Callable, Tuple, List, Literal
from functools import partial

import numpy as np

from mnms.log import create_logger
from mnms.graph.core import TopoGraph, MultiModalGraph, TransitLink
from mnms.graph.search import mobility_nodes_in_radius
from mnms.graph.edition import delete_node_upstream_links, delete_node_downstream_links
from mnms.tools.exceptions import PathNotFound
from mnms.demand.user import User


log = create_logger(__name__)


def dijkstra(G: TopoGraph, user: User, cost: str) -> float:
    """Simple dijkstra shortest path algorithm, it set the `path` attribute of the User with the computed shortest
    path

    Parameters
    ----------
    G: TopoGraph
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
    log.debug(f'Dist : {dist}')

    while len(vertices) > 0:
        d = {v:dist[v] for v in vertices}
        u = min(d, key=d.get)
        vertices.remove(u)
        log.debug(f'Prev {prev}')
        log.debug(f"Curr Node {u}")

        if u == destination:
            log.debug(f"Found destination {u}")
            path = deque()
            if prev[u] is not None or u == origin:
                while u is not None:
                    path.appendleft(u)
                    u = prev[u]
            user.path = list(path)
            return dist[destination]

        for neighbor in G.get_node_neighbors(u):
            log.debug(f"Neighbor Node {neighbor}")
            if neighbor in vertices:

                # Check if next node mobility service is available for the user
                link = G.links[(u, neighbor)]
                alt = dist[u] + G.links[(u, neighbor)].costs[cost]
                if isinstance(link, TransitLink):
                    if user.available_mobility_service is not None:
                        if G.nodes[link.downstream_node].mobility_service not in user.available_mobility_service:
                            alt = float('inf')

                if alt < dist[neighbor]:
                    dist[neighbor] = alt
                    prev[neighbor] = u


def astar(G: TopoGraph, user: User, cost: str, heuristic: Callable[[str, str], float]) -> float:
    """A* shortest path algorithm, it set the `path` attribute of the User with the computed shortest
    path

    Parameters
    ----------
    G: TopoGraph
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
            tentative_gscore = gscore[current] + G.links[(current, neighbor)].costs[cost]
            if isinstance(link, TransitLink):
                if user.available_mobility_service is not None:
                    if G.nodes[link.downstream_node].mobility_service not in user.available_mobility_service:
                        tentative_gscore = float('inf')

            if tentative_gscore < gscore[neighbor]:
                prev[neighbor] = current
                gscore[neighbor] = tentative_gscore
                fscore[neighbor] = gscore[neighbor] + heuristic(current, destination)
                if neighbor not in discovered_nodes:
                    discovered_nodes.add(neighbor)

    return float('inf')


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
                          walk_speed: float = 1.4) -> float:
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
        user_pos_origin = user.origin
        user_pos_destination = user.destination

        current_radius = radius
        while True:
            service_nodes_origin, dist_origin = mobility_nodes_in_radius(user_pos_origin, mmgraph, current_radius)
            service_nodes_destination, dist_destination = mobility_nodes_in_radius(user_pos_destination, mmgraph,
                                                                                   current_radius)

            if len(service_nodes_destination) == 0 or len(service_nodes_destination) == 0:
                current_radius += growth_rate_radius
            else:
                start_node = f"_{user.id}_START"
                end_node = f"_{user.id}_END"

                mmgraph.mobility_graph.add_node(start_node, 'WALK')
                mmgraph.mobility_graph.add_node(end_node, 'WALK')

                log.debug(f"Create start artificial links with: {service_nodes_origin}")
                # print(dist_origin[0]/walk_speed)
                for ind, n in enumerate(service_nodes_origin):
                    mmgraph.connect_mobility_service(start_node + '_' + n, start_node, n,
                                                     {'time': dist_origin[ind] / walk_speed,
                                                      'length': dist_origin[ind]})

                log.debug(f"Create end artificial links with: {service_nodes_destination}")
                for ind, n in enumerate(service_nodes_destination):
                    mmgraph.connect_mobility_service(n + '_' + end_node, n, end_node,
                                                     {'time': dist_destination[ind] / walk_speed,
                                                      'length': dist_destination[ind]})

                user.origin = start_node
                user.destination = end_node

                cost_path = sh_algo(mmgraph.mobility_graph, user, cost)

                # Clean the graph from artificial nodes

                log.debug(f"Clean graph")

                delete_node_downstream_links(mmgraph.mobility_graph, start_node)
                delete_node_upstream_links(mmgraph.mobility_graph, end_node, service_nodes_destination)
                for n in service_nodes_origin:
                    del mmgraph._connection_services[(start_node, n)]
                for n in service_nodes_destination:
                    del mmgraph._connection_services[(n, end_node)]

                user.origin = user_pos_origin
                user.destination = user_pos_destination

                if cost_path != float('inf'):
                    break

                current_radius += growth_rate_radius

        del user.path[0]
        del user.path[-1]

        return cost_path

    else:

        origin = user.origin
        destination = user.destination
        start_nodes = [n for n in mmgraph.mobility_graph.get_node_references(origin)]
        end_nodes = [n for n in mmgraph.mobility_graph.get_node_references(destination)]

        if len(start_nodes) == 0:
            log.warning(f"There is no mobility service connected to origin node {origin}")
            raise PathNotFound(origin, destination)

        if len(end_nodes) == 0:
            log.warning(f"There is no mobility service connected to destination node {destination}")
            raise PathNotFound(origin, destination)

        start_node = f"START_{origin}_{destination}"
        end_node = f"END_{origin}_{destination}"
        log.debug(f"Create artitificial nodes: {start_node}, {end_node}")

        mmgraph.mobility_graph.add_node(start_node, 'NULL')
        mmgraph.mobility_graph.add_node(end_node, 'NULL')

        log.debug(f"Create start artificial links with: {start_nodes}")
        virtual_cost = {cost: 0}
        virtual_cost.update({'time': 0})
        for n in start_nodes:
            mmgraph.connect_mobility_service(start_node + '_' + n, start_node, n, virtual_cost)

        log.debug(f"Create end artificial links with: {end_nodes}")
        for n in end_nodes:
            mmgraph.connect_mobility_service(n + '_' + end_node, n, end_node, virtual_cost)

        user.origin = start_node
        user.destination = end_node

        # Compute paths

        log.debug(f"Compute path")

        cost_path = sh_algo(mmgraph.mobility_graph, user, cost)

        # Clean the graph from artificial nodes

        log.debug(f"Clean graph")

        delete_node_downstream_links(mmgraph.mobility_graph, start_node)
        delete_node_upstream_links(mmgraph.mobility_graph, end_node, end_nodes)
        for n in start_nodes:
            del mmgraph._connection_services[(start_node, n)]
        for n in end_nodes:
            del mmgraph._connection_services[(n, end_node)]

        user.origin = origin
        user.destination = destination

        if cost_path == float('inf'):
            log.warning(f"Path not found for {user}")
            raise PathNotFound(origin, destination)

        del user.path[0]
        del user.path[-1]

        return cost_path


def compute_n_best_shortest_path(mmgraph: MultiModalGraph,
                                 user: User,
                                 npath: int,
                                 cost: str='length',
                                 algorithm: Literal['astar', 'dijkstra']='astar',
                                 heuristic: Callable[[str, str], float]=None,
                                 scale_factor: float = 10,
                                 radius:float = 500,
                                 growth_rate_radius: float = 50,
                                 walk_speed: float = 1.4) -> Tuple[List[List[str]], List[float], List[float]]:
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

        user_pos_origin = user.origin
        user_pos_destination = user.destination

        current_radius = radius
        while True:
            service_nodes_origin, dist_origin = mobility_nodes_in_radius(user_pos_origin, mmgraph, current_radius)
            service_nodes_destination, dist_destination = mobility_nodes_in_radius(user_pos_destination, mmgraph,
                                                                                   current_radius)

            if len(service_nodes_destination) == 0 or len(service_nodes_destination) == 0:
                current_radius += growth_rate_radius
                log.info(f"No service found, increase radius of search: {current_radius}")
            else:
                start_node = f"_{user.id}_START"
                end_node = f"_{user.id}_END"

                mmgraph.mobility_graph.add_node(start_node, 'WALK')
                mmgraph.mobility_graph.add_node(end_node, 'WALK')

                log.debug(f"Create start artificial links with: {service_nodes_origin}")
                # print(dist_origin[0]/walk_speed)
                for ind, n in enumerate(service_nodes_origin):
                    mmgraph.connect_mobility_service(start_node + '_' + n, start_node, n,
                                                     {'time': dist_origin[ind] / walk_speed,
                                                      'length': dist_origin[ind]})

                log.debug(f"Create end artificial links with: {service_nodes_destination}")
                for ind, n in enumerate(service_nodes_destination):
                    mmgraph.connect_mobility_service(n + '_' + end_node, n, end_node,
                                                     {'time': dist_destination[ind] / walk_speed,
                                                      'length': dist_destination[ind]})

                user.origin = start_node
                user.destination = end_node

                cost_path = sh_algo(mmgraph.mobility_graph, user, cost)

                if cost_path != float('inf'):
                    counter = 0
                    similar_path = 0
                    while counter < npath:
                        c = sh_algo(mmgraph.mobility_graph, user, cost)

                        del user.path[0]
                        del user.path[-1]

                        # Only one possible path
                        if len(user.path) == 1:
                            paths.append(user.path[:])
                            penalized_costs.append(c)
                            break

                        for ni in range(len(user.path) - 1):
                            nj = ni + 1
                            link = topograph_links[(user.path[ni], user.path[nj])]
                            if (user.path[ni], user.path[nj]) not in modified_link_cost:
                                modified_link_cost[(user.path[ni], user.path[nj])] = link.costs[cost]
                            link.costs[cost] = link.costs[cost] * scale_factor

                        if len(paths) > 0:
                            current_path = set(user.path)
                            for p in paths:
                                p = set(p)
                                if p == current_path:
                                    similar_path += 1
                                    break
                            else:
                                counter += 1
                                paths.append(user.path[:])
                                penalized_costs.append(c)
                        else:
                            counter += 1
                            paths.append(user.path[:])
                            penalized_costs.append(c)

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

                    user.origin = user_pos_origin
                    user.destination = user_pos_destination

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

                    user.origin = user_pos_origin
                    user.destination = user_pos_destination

    else:

        counter = 0
        while counter < npath:
            c = compute_shortest_path(mmgraph, user, cost, algorithm, heuristic)
            for ni in range(len(user.path) - 1):
                nj = ni + 1
                link = topograph_links[(user.path[ni], user.path[nj])]
                if (user.path[ni], user.path[nj]) not in modified_link_cost:
                    modified_link_cost[(user.path[ni], user.path[nj])] = link.costs[cost]
                link.costs[cost] = link.costs[cost] * scale_factor

            if len(paths) > 0:
                current_path = set(user.path)
                for p in paths:
                    p = set(p)
                    if p == current_path:
                        break
                else:
                    counter += 1
                    paths.append(user.path[:])
                    penalized_costs.append(c)
            else:
                counter += 1
                paths.append(user.path[:])
                penalized_costs.append(c)

        for lnodes, saved_cost in modified_link_cost.items():
            mmgraph.mobility_graph.links[lnodes].costs[cost] = saved_cost

    user.path = None

    real_costs = [sum(topograph_links[(p[n], p[n+1])].costs[cost] for n in range(len(p)-1)) for p in paths]

    return paths, real_costs, penalized_costs





