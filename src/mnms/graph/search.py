from typing import List, Tuple, Iterable
import numpy as np


def nearest_mobility_service(pos:List[float], mmgraph: 'MultiModalGraph', service: str) -> str:
    """Search the nearest mobility service node from a position

    Parameters
    ----------
    pos: list(float)
        The position to consider
    mmgraph: MultiModalGraph
        The MultiModalGraph
    service: str
        Mobility service id to find the closest node

    Returns
    -------
    str
        Node id

    """
    service_nodes = [mmgraph.mobility_graph.nodes[n].reference_node for n in mmgraph._mobility_services[service].nodes]
    service_pos = np.array([mmgraph.flow_graph.nodes[n].pos for n in service_nodes])
    return service_nodes[np.argmin(np.linalg.norm(service_pos-pos, axis=1))]


def mobility_nodes_in_radius(pos:Iterable[float], mmgraph:'MultiModalGraph', radius:float) -> Tuple[List[str], List[float]]:
    """Search all the mobility node inside a radius

    Parameters
    ----------
    pos: list(float)
        Center of the radius search
    mmgraph: MultiModalGraph
        The MultiModalGraph to use for the search
    radius: float
        The radius of search

    Returns
    -------
    list(str), list(float)
        The node ids and the distances from the center position

    """
    nodes = [n for n in mmgraph.mobility_graph.nodes.values()]
    service_nodes = np.array([n.id for n in nodes], dtype=str)
    service_pos = np.array([mmgraph.flow_graph.nodes[n.reference_node].pos for n in nodes])

    dists = np.linalg.norm(service_pos-pos, axis=1)
    mask = dists <= radius
    return service_nodes[mask], dists[mask]
