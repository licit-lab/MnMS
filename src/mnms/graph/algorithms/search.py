from typing import List
from mnms.graph import MultiModalGraph
import numpy as np


def nearest_mobility_service(pos:List[float], mmgraph: MultiModalGraph, service: str):
    service_nodes = [mmgraph.mobility_graph.nodes[n].reference_node for n in mmgraph._mobility_services[service].nodes]
    service_pos = np.array([mmgraph.flow_graph.nodes[n].pos for n in service_nodes])
    return service_nodes[np.argmin(np.linalg.norm(service_pos-pos, axis=1))]
