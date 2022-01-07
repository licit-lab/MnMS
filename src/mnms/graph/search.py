from typing import List, Tuple, Iterable
import numpy as np


def nearest_mobility_service(pos:List[float], mmgraph: 'MultiModalGraph', service: str):
    service_nodes = [mmgraph.mobility_graph.nodes[n].reference_node for n in mmgraph._mobility_services[service].nodes]
    service_pos = np.array([mmgraph.flow_graph.nodes[n].pos for n in service_nodes])
    return service_nodes[np.argmin(np.linalg.norm(service_pos-pos, axis=1))]


def mobility_nodes_in_radius(pos:Iterable[float], mmgraph:'MultiModalGraph', radius:float) -> Tuple[List[str], List[float]]:
    nodes = [n for n in mmgraph.mobility_graph.nodes.values()]
    service_nodes = np.array([n.id for n in nodes], dtype=str)
    service_pos = np.array([mmgraph.flow_graph.nodes[n.reference_node].pos for n in nodes])

    dists = np.linalg.norm(service_pos-pos, axis=1)
    mask = dists <= radius
    return service_nodes[mask], dists[mask]
