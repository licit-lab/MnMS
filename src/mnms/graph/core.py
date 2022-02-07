from typing import Dict, Tuple, List, Union, Set
from collections import defaultdict, ChainMap
from itertools import combinations

import numpy as np

from mnms.graph.search import mobility_nodes_in_radius
from mnms.tools.exceptions import DuplicateNodesError, DuplicateLinksError
from mnms.graph.elements import GeoNode, TopoNode, GeoLink, ConnectionLink, TransitLink, Zone


class OrientedGraph(object):
    """Basic class for an oriented graph.

    Attributes
    ----------
    nodes : dict
        Dict of nodes, key is the id of node, value is either a GeoNode or a Toponode
    links : type
        Dict of links, key is the tuple of nodes, value is either a GeoLink or a TopoLink

    """
    def __init__(self):
        self.nodes: Dict[str, Union[GeoNode, TopoNode]] = dict()
        self.links: Dict[Tuple[str, str], Union[TransitLink, ConnectionLink, GeoLink]] = dict()
        self._adjacency: Dict[str, Set[str]] = dict()
        self._map_lid_nodes: Dict[str, Tuple[str, str]] = dict()

    def get_node_neighbors(self, nodeid: str) -> Set[str]:
        return self._adjacency[nodeid]

    @property
    def nb_nodes(self):
        return len(self.nodes)

    @property
    def nb_links(self):
        return len(self.links)

    def delete_node(self, nid):
        assert nid in self.nodes, f"Node '{nid}' not in graph"
        del self.nodes[nid]
        del self._adjacency[nid]
        [adj.discard(nid) for adj in self._adjacency.values()]

    def delete_link(self, lid):
        assert lid in self._map_lid_nodes, f"Link '{lid}' not in graph"
        nodes = self._map_lid_nodes[lid]
        del self.links[nodes]
        del self._map_lid_nodes[lid]
        self._adjacency[nodes[0]].remove(nodes[1])


class TopoGraph(OrientedGraph):
    """Class implementing a purely topological oriented graph
    """
    def __init__(self):
        super(TopoGraph, self).__init__()
        self.node_referencing = defaultdict(list)

    def add_node(self, nid: str, mobility_service:str, ref_node=None) -> None:
        assert nid not in self.nodes, f"Node '{nid}' already in graph"
        new_node = TopoNode(nid, mobility_service, ref_node)
        self._add_node(new_node)

    def _add_node(self, node:TopoNode):
        self.nodes[node.id] = node
        if node.reference_node is not None:
            self.node_referencing[node.reference_node].append(node.id)
        self._adjacency[node.id] = set()

    def add_link(self, lid:str, upstream_node:str, downstream_node:str, costs:Dict[str, float],
                 reference_links:List[str]=None, reference_lane_ids:List[int]=None, mobility_service:str=None) -> None:
        assert (upstream_node, downstream_node) not in self.links, f"Nodes {upstream_node}, {downstream_node} already connected"
        assert lid not in self._map_lid_nodes, f"Link id {lid} already exist"

        link = ConnectionLink(lid, upstream_node, downstream_node, costs, reference_links, reference_lane_ids, mobility_service)
        self._add_link(link)

    def _add_link(self, link: [ConnectionLink, TransitLink]):
        self.links[(link.upstream_node, link.downstream_node)] = link
        self._map_lid_nodes[link.id] = (link.upstream_node, link.downstream_node)
        self._adjacency[link.upstream_node].add(link.downstream_node)


class GeoGraph(OrientedGraph):
    def add_node(self, nodeid: str, pos: List[float]) -> None:
        assert nodeid not in self.nodes

        node = GeoNode(nodeid, pos)
        self._add_node(node)

    def _add_node(self, node:GeoNode):
        self.nodes[node.id] = node
        self._adjacency[node.id] = set()

    def add_link(self, lid, upstream_node: str, downstream_node: str, length:float=None, nb_lane:int=1) -> None:
        assert (upstream_node, downstream_node) not in self.links
        if length is None:
            length = np.linalg.norm(self.nodes[upstream_node].pos - self.nodes[downstream_node].pos)
        link = GeoLink(lid, upstream_node, downstream_node, length=length, nb_lane=nb_lane)
        self._add_link(link)

    def _add_link(self, link:GeoLink):
        self.links[(link.upstream_node, link.downstream_node)] = link
        self._map_lid_nodes[link.id] = (link.upstream_node, link.downstream_node)
        self._adjacency[link.upstream_node].add(link.downstream_node)

    def extract_subgraph(self, nodes:set):
        subgraph = self.__class__()
        for n in nodes:
            subgraph.add_node(n, self.nodes[n].pos)

        [subgraph.add_link(self.links[(u_node, d_node)].id, u_node, d_node) for u_node, d_node in self.links if u_node in nodes and d_node in nodes]

        return subgraph


class ComposedTopoGraph(TopoGraph):
    def __init__(self):
        self.nodes = ChainMap()
        self.links = ChainMap()
        self._adjacency = ChainMap()
        self._map_lid_nodes = ChainMap()
        self._node_referencing = []

        # self.graphs = dict()
        # self._nb_subgraph = 0

    def add_topo_graph(self, graph: TopoGraph):
        self.nodes.maps.append(graph.nodes)
        self.links.maps.append(graph.links)
        self._adjacency.maps.append(graph._adjacency)
        self._map_lid_nodes.maps.append(graph._map_lid_nodes)
        self._node_referencing.append(graph.node_referencing)

        # self.graphs[gid] = self._nb_subgraph
        # self._nb_subgraph += 1

        self.check()

    def get_node_references(self, nid: str):
        node_refs = []
        for ref in self._node_referencing:
            node_refs.extend(ref[nid])
        return node_refs

    def connect_topo_graphs(self, lid:str, unid: str, dnid: str, costs:dict={}):
        assert (unid, dnid) not in self.links, f"Nodes {unid}, {dnid} already in graph"
        assert lid not in self._map_lid_nodes, f"Link id {lid} already exist"

        link = TransitLink(lid, unid, dnid, costs)
        self.links[(unid, dnid)] = link
        self._adjacency[unid].add(dnid)
        self._map_lid_nodes[lid] = (unid, dnid)

    def check_unicity_node(self, nid):
        appearance = 0
        for i in range(len(self.nodes.maps)):
            if nid in self.nodes.maps[i]:
                appearance += 1
        if appearance > 1:
            raise DuplicateNodesError({nid})

    def check_unicity_link(self, lid):
        appearance = 0
        for i in range(len(self.links.maps)):
            if lid in self.links.maps[i]:
                appearance += 1
        if appearance > 1:
            raise DuplicateNodesError({lid})

    def check_unicity_nodes(self):
        all_nodes = set()
        intersection_nodes = set()
        for i in range(len(self.nodes.maps)):
            curr_nodes = set(self.nodes.maps[i].keys())
            intersection_nodes.update(all_nodes.intersection(curr_nodes))
            all_nodes.update(curr_nodes)

        if len(intersection_nodes) > 0:
            raise DuplicateNodesError(intersection_nodes)

    def check_unicity_links(self):
        all_links = set()
        intersection_links = set()
        for i in range(len(self._map_lid_nodes.maps)):
            curr_links = set(self._map_lid_nodes.maps[i].keys())
            intersection_links.update(all_links.intersection(curr_links))
            all_links.update(curr_links)

        if len(intersection_links) > 0:
            raise DuplicateLinksError(intersection_links)

    def check(self):
        self.check_unicity_nodes()
        self.check_unicity_links()

    def compute_cost_path(self, path:List[str], cost):
        res = 0
        for i in range(len(path)-1):
            res += self.links[(path[i],path[i+1])].costs[cost]
        return res


class MultiModalGraph(object):
    """MultiModalGraph class, it holds the geometry of the network in a GeoGraph and the mobility services in
    a TopoGraph

    Attributes
    ----------
    flow_graph: GeoGraph
        Graph representing the geometry of the network
    mobility_graph: TopoGraph
        Graph representing all the mobility services and their connexions
    zones: dict
        Dict of reservoirs define on flow_graph
    """
    def __init__(self, nodes:Dict[str, Tuple[float]]={}, links:Dict[str, Tuple[float]]= {}, mobility_services=[]):
        self.flow_graph = GeoGraph()
        self.mobility_graph = ComposedTopoGraph()
        self.zones = dict()

        self._connection_services = dict()
        self._mobility_services = dict()

        [self.flow_graph.add_node(nid, pos) for nid, pos in nodes.items()]
        [self.flow_graph.add_link(lid, unid, dnid) for lid, (unid, dnid) in  links.items()]
        [serv.connect_graph(self) for serv in mobility_services]

    def add_mobility_service(self, service: "BaseMobilityService"):
        self._mobility_services[service.id] = service
        self.mobility_graph.add_topo_graph(service)

    def connect_mobility_service(self, lid: str,  upstream_node: str, downstream_node:str, costs):
        upstream_service = self.mobility_graph.nodes[upstream_node].mobility_service
        downstream_service = self.mobility_graph.nodes[downstream_node].mobility_service
        assert upstream_service != downstream_service, f"Upstream service must be different from downstream service ({upstream_service})"
        assert "time" in costs, "time must pe present in the cost dictionnay"

        link = TransitLink(lid, upstream_node, downstream_node, costs)
        self.mobility_graph._add_link(link)
        self._connection_services[(upstream_node, downstream_node)] = lid

    def add_zone(self, sid: str, links: List[str]):
        for lid in links:
            nodes = self.flow_graph._map_lid_nodes[lid]
            self.flow_graph.links[nodes].zone = sid
        self.zones[sid] = Zone(sid, links)

    def get_extremities(self):
        extremities = {nid for nid, neighbors in self.flow_graph._adjacency.items() if len(neighbors) == 1}
        return extremities

    def construct_hub(self, nid:str, radius:float, walk_speed:float=1.4, exclusion_matrix:Dict[str, Set[str]]={}):
        assert nid in self.flow_graph.nodes, f"{nid} is not in the flow graph"
        node = self.flow_graph.nodes[nid]
        node_pos = node.pos
        flow_graph_nodes = self.flow_graph.nodes

        service_nodes, _ = mobility_nodes_in_radius(node_pos, self, radius)

        for ni, nj in combinations(service_nodes, 2):
            node_ni = self.mobility_graph.nodes[ni]
            node_nj = self.mobility_graph.nodes[nj]

            mservice_ni = self._mobility_services[node_ni.mobility_service]
            mservice_nj = self._mobility_services[node_nj.mobility_service]

            if type(mservice_ni) != type(mservice_nj):
                exclusion_ni = exclusion_matrix.get(node_ni.mobility_service, set())
                exclusion_nj = exclusion_matrix.get(node_nj.mobility_service, set())
                dist = np.linalg.norm(flow_graph_nodes[node_nj.reference_node].pos - flow_graph_nodes[node_ni.reference_node].pos)
                if node_nj.mobility_service not in exclusion_ni:
                    c = {'length': dist, 'time': dist / walk_speed, 'speed': walk_speed}
                    cost_connect = mservice_nj.connect_to_service(nj)
                    for key, val in cost_connect.items():
                        if key in c:
                            c[key] += val
                    self.mobility_graph.add_link(f'_WALK_{ni}_{nj}', ni, nj, c, mobility_service='HUB')

                if node_ni.mobility_service not in exclusion_nj:
                    c = {'length': dist, 'time': dist / walk_speed, 'speed': walk_speed}
                    cost_connect = mservice_nj.connect_to_service(nj)
                    for key, val in cost_connect.items():
                        if key in c:
                            c[key] += val
                    self.mobility_graph.add_link(f'_WALK_{nj}_{ni}', nj, ni, c, mobility_service='HUB')