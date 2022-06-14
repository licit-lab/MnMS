from timeit import default_timer as timer
from typing import Callable, Union, List, Dict

import pandas as pd

from mnms.graph.core import TopoGraph
from mnms.graph.elements import TransitLink
from mnms.graph.shortest_path import Path, _weight_computation

_WEIGHT_COST_TYPE = Union[str, Callable[[Dict[str, float]], float]]


def measure(func: Callable):
    def inner(*args, **kwargs):
        print(f'---> Calling {func.__name__}()')
        start = timer()
        ret = func(*args, **kwargs)
        elapsed_sec = timer() - start
        print(f'---> Done {func.__name__}(): {elapsed_sec:.3f} secs')
        return ret
    return inner


class Measure:
    def __init__(self, txt: str, stack=None):
        self._txt = txt
        self._stack = stack

    def __enter__(self):
        self._t0 = timer()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._stack:
            self._stack.value += timer() - self._t0
        else:
            print(f"{self._txt} time = {timer() - self._t0}")

# @measure
def dijkstra_v2(graph: TopoGraph,
                origin:str,
                destination:str,
                cost: _WEIGHT_COST_TYPE,
                available_layers: Union[List[str], None]) -> Path:
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
        vertices.add(v)

    dist[origin] = 0
    prev[origin] = None

    search_list = set()
    search_list.add((0, origin))

    # neighbor_time = py_object(0)
    # search_min = py_object(0)
    # log_time = py_object(0)

    log_msg = []

    while search_list:
        u = min(search_list)
        search_list.remove(u)
        u = u[1]
        vertices.remove(u)

        if u == destination:
            nodes = []
            if prev[u] is not None or u == origin:
                while u is not None:
                    nodes.append(u)
                    u = prev[u]
            nodes.reverse()

            # print(f"log_time = {log_time.value}")
            # print(f"neighbor_time = {neighbor_time.value}")
            # print(f"search_min = {search_min.value}")
            return Path(dist[destination], nodes)

        # with Measure("", neighbor_time):
        for links_id in graph.nodes[u].links_id:
            link = graph.links_from_id[links_id]
            neighbor = link.downstream
            if neighbor in vertices:

                # Check if next node mobility service is available for the user
                alt = dist[u] + cost_func(link.costs)
                if isinstance(link, TransitLink):
                    if available_layers is not None:
                        dnode_layer = graph.nodes[link.downstream_node].layer
                        if dnode_layer is not None and dnode_layer not in available_layers:
                            alt = float('inf')

                if alt < dist.get(neighbor, float('inf')):
                    dist[neighbor] = alt
                    prev[neighbor] = u

                search_list.add((alt, neighbor))

    return Path(float('inf'))


def dijkstra_multi_dest(graph: TopoGraph,
                        origin:str,
                        destination: List[str],
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
    ret = {}
    cost_func = _weight_computation(cost)

    vertices = set()
    dist = dict()

    for v in graph.nodes:
        vertices.add(v)

    dist[origin] = (0, None)
    search_list = set()
    search_list.add((0, origin))

    while search_list and destination:
        u = min(search_list)
        search_list.remove(u)
        u = u[1]
        vertices.remove(u)
        if u == destination:
            dest = u
            nodes = []
            if dist[u][1] is not None or u == origin:
                while u is not None:
                    nodes.append(u)
                    u = dist[u][1]
            nodes.reverse()
            ret[dest] = Path(dist[dest], nodes)
            destination.remove(u)

        for link in graph.nodes[u].links:
            neighbor = link.downstream
            if neighbor in vertices:

                # Check if next node mobility service is available for the user
                alt = dist[u][0] + cost_func(link.costs)
                if isinstance(link, TransitLink):
                    if available_layers is not None:
                        dnode_layer = graph.nodes[link.downstream_node].layer
                        if dnode_layer is not None and dnode_layer not in available_layers:
                            alt = float('inf')

                if alt < dist.get(neighbor, [float('inf')])[0]:
                    dist[neighbor] = (alt, u)

                search_list.add((alt, neighbor))

    if ret:
        return ret
    return Path(float('inf'))


def dijkstra_vold(graph: TopoGraph,
                  origin:str,
                  destination:str,
                  cost: _WEIGHT_COST_TYPE,
                  available_layers:Union[List[str], None],
                  path_df: pd.DataFrame) -> Path:
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

    for v in graph.nodes:
        vertices.add(v)

    dist[origin] = (0, None)

    search_list2 = set()
    search_list2.add(origin)
    path_df.loc[(origin, ""), :] = [0, None, ""]

    # neighbor_time = py_object(0)
    # search_min = py_object(0)
    # log_time = py_object(0)

    while search_list2:
        idx_min = path_df.loc[list(search_list2), "cost"].astype(float).idxmin()
        line = path_df.loc[idx_min]
        u = idx_min[0]
        search_list2.remove(u)
        vertices.remove(u)

        if u == destination:
            nodes = []
            if dist[u][1] is not None or u == origin:
                while u is not None:
                    nodes.append(u)
                    u = path_df.loc[u, "prev"][0]

                nodes.reverse()

            return Path(dist[destination][0], nodes)

        for links_id in graph.nodes[u].links:
            link = graph.links_from_id[links_id]
            neighbor = link.downstream
            if neighbor in vertices:

                # Check if next node mobility service is available for the user
                alt = line["cost"] + cost_func(link.costs)
                if isinstance(link, TransitLink):
                    if available_layers is not None:
                        dnode_layer = graph.nodes[link.downstream_node].layer
                        if dnode_layer is not None and dnode_layer not in available_layers:
                            alt = float('inf')

                if alt < dist.get(neighbor, [float('inf')])[0]:
                    dist[neighbor] = (alt, u)
                    path_df.loc[(neighbor, link.id), :] = [alt, u, line.history + " " + line.name[1]]
                search_list2.add(neighbor)

    return Path(float('inf'))

