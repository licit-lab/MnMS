from collections import defaultdict

import numpy as np

from mnms.graph.core import MultiModalGraph


def walk_connect(mmgraph:MultiModalGraph, radius:float=100, walk_speed=1.4):
    mappping_nodes = {n:mmgraph.mobility_graph.get_node_references(n) for n in mmgraph.flow_graph.nodes}
    for ni in mmgraph.flow_graph.nodes.values():
        for nj in mmgraph.flow_graph.nodes.values():
            if ni.id != nj.id:
                dist = np.linalg.norm(nj.pos-ni.pos)
                if dist < radius:
                    for mserv_node_i in mappping_nodes[ni.id]:
                        upstream_node = mmgraph.mobility_graph.nodes[mserv_node_i]
                        for mserv_node_j in mappping_nodes[nj.id]:
                            downstream_node = mmgraph.mobility_graph.nodes[mserv_node_j]
                            if upstream_node.mobility_service != downstream_node.mobility_service:
                                label = f'_Walk_{upstream_node.id}_{downstream_node.id}'
                                cost = mmgraph._mobility_services[downstream_node.mobility_service].connect_to_service(downstream_node.id)
                                cost['time'] += walk_speed*dist
                                mmgraph.mobility_graph.connect_topo_graphs(label, upstream_node.id, downstream_node.id, cost)

