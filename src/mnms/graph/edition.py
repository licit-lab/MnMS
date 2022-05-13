from typing import List

import numpy as np

from mnms.graph.core import OrientedGraph, MultiModalGraph
from mnms.tools.progress import ProgressBar


def delete_node(graph: OrientedGraph, nid:str, upstream_nodes:List[str]=[]):
    """Safe deletion of a node in a graph

    Parameters
    ----------
    graph: OrientedGraph
        Graph in which to remove a node
    nid: str
        Id of the node
    upstream_nodes: list(str)
        List of upstream nodes to the node to delete for adjacency cleaning

    Returns
    -------
    None

    """
    assert nid in graph.nodes, f"Node '{nid}' not in graph"
    del graph.nodes[nid]
    [graph.nodes[up].adj.remove(nid) for up in upstream_nodes]


def delete_link_from_id(graph: OrientedGraph, lid:str):
    """Safe deletion of a link in a graph

    Parameters
    ----------
    graph: OrientedGraph
        Graph in which to remove the link
    lid: str
        Id of the link

    Returns
    -------
    None

    """
    assert lid in graph._map_lid_nodes, f"Link '{lid}' not in graph"
    nodes = graph._map_lid_nodes[lid]
    del graph.links[nodes]
    del graph._map_lid_nodes[lid]
    graph.nodes[nodes[0]].adj.remove(nodes[1])


def delete_link_from_extremities(graph: OrientedGraph, upstream:str, downstream:str):
    """Safe deletion of a link in a graph from its extremities

    Parameters
    ----------
    graph: OrientedGraph
        Graph in which to remove the link
    upstream: str
        Upstream node id
    downstream: str
        Downstreqm node id

    Returns
    -------
    None

    """
    nodes = (upstream, downstream)
    assert nodes in graph.links, f"Link '{nodes}' not in graph"
    lid = graph.links[nodes].id
    del graph.links[nodes]
    del graph._map_lid_nodes[lid]
    graph.nodes[nodes[0]].adj.remove(nodes[1])


def delete_node_downstream_links(graph: OrientedGraph, nid:str):
    """Delete a node and all its downstream links

    Parameters
    ----------
    graph: OrientedGraph
        Graph in which to remove the link
    nid: str
        Node id to delete

    Returns
    -------
    None

    """
    downstream_nodes = set(graph.nodes[nid].adj)
    for nd in downstream_nodes:
        delete_link_from_extremities(graph, nid, nd)
    delete_node(graph, nid)


def delete_node_upstream_links(graph: OrientedGraph, nid:str, upstream_nodes:List[str]):
    """Delete a node and all its upstream links

    Parameters
    ----------
    graph: OrientedGraph
        Graph in which to remove the link
    nid: str
        Node id to delete
    upstream_nodes: list(str)
        List of the upstream node ids

    Returns
    -------
    None

    """
    for nd in upstream_nodes:
        delete_link_from_extremities(graph, nd, nid)
    delete_node(graph, nid)



def walk_connect(mmgraph:MultiModalGraph, radius:float=100, walk_speed:float=1.4):
    mappping_nodes = {n:mmgraph.mobility_graph.get_node_references(n) for n in mmgraph.flow_graph.nodes}

    for ni in ProgressBar(mmgraph.flow_graph.nodes.values(), text="Walk"):
        if len(mappping_nodes[ni.id]) > 0:
            for nj in mmgraph.flow_graph.nodes.values():
                dist = np.linalg.norm(nj.pos-ni.pos)
                if dist < radius:
                    for mserv_node_i in mappping_nodes[ni.id]:
                        upstream_node = mmgraph.mobility_graph.nodes[mserv_node_i]
                        for mserv_node_j in mappping_nodes[nj.id]:
                            downstream_node = mmgraph.mobility_graph.nodes[mserv_node_j]
                            if upstream_node.layer != downstream_node.layer:
                                label = f'_WALK_{upstream_node.id}_{downstream_node.id}'
                                cost = mmgraph._mobility_services[downstream_node.layer].connect_to_service(downstream_node.id)
                                cost['time'] += walk_speed*dist
                                cost['length'] = dist
                                mmgraph.mobility_graph.connect_topo_graphs(label, upstream_node.id, downstream_node.id, cost)
