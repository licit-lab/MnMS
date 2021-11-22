from typing import List


import numpy as np


def nearest_mobility_service(pos:List[float], mmgraph, service: str):
    service_nodes = [n for n in mmgraph._mobility_services[service].nodes]
    service_pos = np.array([mmgraph.flow_graph.nodes[n].pos for n in service_nodes])
    return service_nodes[np.argmin(np.linalg.norm(service_pos-pos, axis=1))]
