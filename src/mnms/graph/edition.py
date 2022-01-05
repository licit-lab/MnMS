from typing import List

from mnms.graph.core import OrientedGraph


def delete_node(graph: OrientedGraph, nid:str, upstream_nodes:List[str]=[]):
    assert nid in graph.nodes, f"Node '{nid}' not in graph"
    del graph.nodes[nid]
    del graph._adjacency[nid]
    [graph._adjacency[up].remove(nid) for up in upstream_nodes]


def delete_link_from_id(graph: OrientedGraph, lid:str):
    assert lid in graph._map_lid_nodes, f"Link '{lid}' not in graph"
    nodes = graph._map_lid_nodes[lid]
    del graph.links[nodes]
    del graph._map_lid_nodes[lid]
    graph._adjacency[nodes[0]].remove(nodes[1])


def delete_link_from_extremities(graph: OrientedGraph, upstream:str, downstream:str):
    nodes = (upstream, downstream)
    assert nodes in graph.links, f"Link '{nodes}' not in graph"
    lid = graph.links[nodes].id
    del graph.links[nodes]
    del graph._map_lid_nodes[lid]
    graph._adjacency[nodes[0]].remove(nodes[1])


def delete_node_downstream_links(graph: OrientedGraph, nid:str):
    downstream_nodes = set(graph.get_node_neighbors(nid))
    for nd in downstream_nodes:
        delete_link_from_extremities(graph, nid, nd)
    delete_node(graph, nid)


def delete_node_upstream_links(graph: OrientedGraph, nid:str, upstream_nodes:List[str]):
    for nd in upstream_nodes:
        delete_link_from_extremities(graph, nd, nid)
    delete_node(graph, nid)