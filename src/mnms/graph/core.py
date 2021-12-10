from typing import Dict, Tuple, List, Union, FrozenSet
from collections import defaultdict, ChainMap
from abc import ABC, abstractmethod
import numpy as np

from mnms.log import logger
from mnms.tools.exceptions import DuplicateNodesError, DuplicateLinksError


class GraphElement(ABC):
    def __init__(self, id: str):
        self.id = id

    @abstractmethod
    def __load__(cls, data: dict):
        pass

    @abstractmethod
    def __dump__(self) -> dict:
        pass


class TopoNode(GraphElement):
    """Class representing a topological node, it can refer to a GeoNode id

    Parameters
    ----------
    id: str
        The identifier for this TopoNode
    ref_node: str
        A reference to GeoNode (default is None)

    """
    def __init__(self, id: str, mobility_service, ref_node:str=None, costs={}):
        super(TopoNode, self).__init__(id)
        self.reference_node = ref_node
        self.mobility_service = mobility_service
        self.costs = {'time': 0, '_default': 1}
        self.costs.update(costs)

    def __repr__(self):
        return f"TopoNode(id={self.id}, ref_node={self.reference_node})"

    @classmethod
    def __load__(cls, data: dict) -> "TopoNode":
        return cls(data['ID'], data['MOBILITY_SERVICE'], data['REF_NODE'], data['COSTS'])

    def __dump__(self) -> dict:
        return {'ID': self.id,
                'REF_NODE': self.reference_node,
                'MOBILITY_SERVICE': self.mobility_service,
                'COSTS': {key: val for key, val in self.costs.items() if key != "_default"}}


class GeoNode(GraphElement):
    """Class representing a geometric node

    Parameters
    ----------
    id: str
        The identifier for this GeoNode
    pos: list
        A list of float of size 2 representing the node position

    """
    def __init__(self, id, pos):
        super(GeoNode, self).__init__(id)
        self.pos = np.array(pos)

    def __repr__(self):
        return f"GeoNode(id={self.id}, pos={self.pos})"

    @classmethod
    def __load__(cls, data: dict) -> "GeoNode":
        return cls(data['ID'], data['POSITION'])

    def __dump__(self) -> dict:
        return {'ID': self.id,
                'POSITION': self.pos.tolist()}

class ConnectionLink(GraphElement):
    """Link between two Mobility Service.

    Parameters
    ----------
    id: str
        The identifier for this TopoLink
    upstream_node: str
        Reference to uptream TopoNode
    downstream_node: str
        Reference to downstream TopoNode
    costs: dict
        Dictionnary of costs
    reference_links: list
        List of references of the associated GeoLinks
    reference_lane_ids: list
        List of index of lane id for each reference_links
    mobility_service: str
        Identifier of the mobility service that use this TopoLink
    """
    def __init__(self, lid, upstream_node, downstream_node, costs=None, reference_links=None, reference_lane_ids=None,
                 mobility_service=None):
        super(ConnectionLink, self).__init__(lid)
        self.upstream_node = upstream_node
        self.downstream_node = downstream_node
        self.costs = {'time': 0, '_default': 1}
        if costs is not None:
            self.costs.update(costs)
        self.reference_links = reference_links if reference_links is not None else []
        self.reference_lane_ids = []
        self.mobility_service = mobility_service

        if reference_links is not None:
            if reference_lane_ids is None:
                self.reference_lane_ids = [0]*len(reference_links)
            else:
                self.reference_lane_ids = reference_lane_ids

    def __repr__(self):
        return f"TransitLink(id={self.id}, upstream={self.upstream_node}, downstream={self.downstream_node})"

    @classmethod
    def __load__(cls, data: dict) -> "ConnectionLink":
        return cls(data['ID'], data['UPSTREAM'], data['DOWNSTREAM'], data['COSTS'], data['REF_LINKS'], data['REF_LANE_IDS'], data['MOBILITY_SERVICE'])

    def __dump__(self) -> dict:
        return {'ID': self.id,
                'UPSTREAM': self.upstream_node,
                'DOWNSTREAM': self.downstream_node,
                'COSTS': {key: val for key, val in self.costs.items() if key != "_default"},
                'REF_LINKS': self.reference_links,
                'REF_LANE_IDS': self.reference_lane_ids,
                'MOBILITY_SERVICE': self.mobility_service}


class TransitLink(GraphElement):
    def __init__(self, lid, upstream_node, downstream_node, costs=None):
        super(TransitLink, self).__init__(lid)
        self.upstream_node = upstream_node
        self.downstream_node = downstream_node
        self.costs = {'time': 0, '_default': 1}
        if costs is not None:
            self.costs.update(costs)


    def __repr__(self):
        return f"ConnectionLink(id={self.id}, upstream={self.upstream_node}, downstream={self.downstream_node})"

    @classmethod
    def __load__(cls, data: dict) -> "TransitLink":
        return cls(data['ID'], data['UPSTREAM'], data['DOWNSTREAM'], data['COSTS'])

    def __dump__(self) -> dict:
        return {'ID': self.id,
                'UPSTREAM': self.upstream_node,
                'DOWNSTREAM': self.downstream_node,
                'COSTS': {key: val for key, val in self.costs.items() if key != "_default"}}


class GeoLink(GraphElement):
    """Link between two GeoNode, define a physical road link

    Parameters
    ----------
    id: str
        The identifier for this TopoLink
    upstream_node: str
        Reference to uptream GeoNode
    downstream_node: str
        Reference to downstream GeoNode
    length:
        Length of the link
    nb_lane: int
        Number of lane on this link (default 1)
    """
    def __init__(self, lid, upstream_node, downstream_node, length, nb_lane=1):
        super(GeoLink, self).__init__(lid)
        self.upstream_node = upstream_node
        self.downstream_node = downstream_node
        self.nb_lane = nb_lane
        self.sensor = None
        self.length = length

    def __repr__(self):
        return f"GeoLink(id={self.id}, upstream={self.upstream_node}, downstream={self.downstream_node}, len={self.length})"

    @classmethod
    def __load__(cls, data: dict) -> "GeoLink":
        return cls(data['ID'], data['UPSTREAM'], data['DOWNSTREAM'], data['LENGTH'], data['NB_LANES'])

    def __dump__(self) -> dict:
        return {'ID': self.id,
                'UPSTREAM': self.upstream_node,
                'DOWNSTREAM': self.downstream_node,
                'LENGTH': self.length,
                'NB_LANES': self.nb_lane}

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
        self.nodes: Dict[str, Union[TopoLink, GeoLink]] = dict()
        self.links: Dict[Tuple[str, str], Union[TransitLink, ConnectionLink, GeoLink]] = dict()
        self._adjacency: Dict[str, List[str]] = dict()
        self._map_lid_nodes: Dict[str, Tuple[str, str]] = dict()

    def get_node_neighbors(self, nodeid: str) -> List[str]:
        return self._adjacency[nodeid]

    @property
    def nb_nodes(self):
        return len(self.nodes)

    @property
    def nb_links(self):
        return len(self.links)


class TopoGraph(OrientedGraph):
    """Class implementing a purely topological oriented graph
    """
    def __init__(self):
        super(TopoGraph, self).__init__()
        self.node_referencing = defaultdict(list)


    def add_node(self, nid: str, mobility_service:str, ref_node=None) -> None:
        assert nid not in self.nodes
        self.nodes[nid] = TopoNode(nid, mobility_service, ref_node)
        if ref_node is not None:
            self.node_referencing[ref_node].append(nid)
        self._adjacency[nid] = set()

    def add_link(self, link: ConnectionLink):
        self.links[(link.upstream_node, link.downstream_node)] = link
        self._map_lid_nodes[link.id] = (link.upstream_node, link.downstream_node)
        self._adjacency[link.upstream_node].add(link.downstream_node)


    def add_connexion_link(self, lid, upstream_node, downstream_node, costs, reference_links=None, reference_lane_ids=None,
                 mobility_service=None) -> None:
        assert (upstream_node, downstream_node) not in self.links, f"Nodes {upstream_node}, {downstream_node} already in graph"
        assert lid not in self._map_lid_nodes, f"Link id {lid} already exist"

        link = ConnectionLink(lid, upstream_node, downstream_node, costs, reference_links, reference_lane_ids, mobility_service)
        self.add_link(link)

    # def add_transit_link(self, lid, upstream_node, downstream_node, costs):
    #     assert (upstream_node, downstream_node) not in self.links, f"Nodes {upstream_node}, {downstream_node} already in graph"
    #     assert lid not in self._map_lid_nodes, f"Link id {lid} already exist"
    #
    #     link = TransitLink(lid, upstream_node, downstream_node, costs)
    #     self.add_link(link)

    # def extract_subgraph(self, nodes:set):
    #     subgraph = self.__class__()
    #     for n in nodes:
    #         subgraph.add_node(n, None)
    #
    #     [subgraph.add_link(self.links[(u_node, d_node)].id, u_node, d_node, self.links[(u_node, d_node)].costs) for u_node, d_node in self.links if u_node in nodes and d_node in nodes]
    #
    #     return subgraph



class ComposedTopoGraph(object):
    def __init__(self):
        self.nodes = ChainMap()
        self.links = ChainMap()
        self._adjacency = ChainMap()
        self._map_lid_nodes = ChainMap()
        self._node_referencing = []

        self.graphs = dict()
        self._nb_subgraph = 0

    def get_node_neighbors(self, nodeid: str) -> List[str]:
        return self._adjacency[nodeid]

    def add_topo_graph(self, gid:str, graph: "TopoGraph"):
        self.nodes.maps.append(graph.nodes)
        self.links.maps.append(graph.links)
        self._adjacency.maps.append(graph._adjacency)
        self._map_lid_nodes.maps.append(graph._map_lid_nodes)
        self._node_referencing.append(graph.node_referencing)

        self.graphs[gid] = self._nb_subgraph
        self._nb_subgraph += 1

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
        appearence = 0
        for i in range(len(self.nodes.maps)):
            if nid in self.nodes.maps[i]:
                appearence += 1
        if appearence > 1:
            raise DuplicateNodesError({nid})

    def check_unicity_link(self, lid):
        appearence = 0
        for i in range(len(self.links.maps)):
            if lid in self.links.maps[i]:
                appearence += 1
        if appearence > 1:
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


class GeoGraph(OrientedGraph):
    """Class implementing a geometrical oriented graph
    """
    def add_node(self, nodeid: str, pos: List[float]) -> None:
        assert nodeid not in self.nodes

        node = GeoNode(nodeid, pos)
        self.nodes[node.id] = node

        self._adjacency[nodeid] = set()

    def add_link(self, lid, upstream_node: str, downstream_node: str, length:float=None, nb_lane:int=1) -> None:
        assert (upstream_node, downstream_node) not in self.links
        if length is None:
            length = np.linalg.norm(self.nodes[upstream_node].pos - self.nodes[downstream_node].pos)
        link = GeoLink(lid, upstream_node, downstream_node, length=length, nb_lane=nb_lane)
        self.links[(upstream_node, downstream_node)] = link
        self._map_lid_nodes[lid] = (upstream_node, downstream_node)
        self._adjacency[link.upstream_node].add(link.downstream_node)


    def extract_subgraph(self, nodes:set):
        subgraph = self.__class__()
        for n in nodes:
            subgraph.add_node(n, self.nodes[n].pos)

        [subgraph.add_link(self.links[(u_node, d_node)].id, u_node, d_node) for u_node, d_node in self.links if u_node in nodes and d_node in nodes]

        return subgraph


class Sensor(GraphElement):
    def __init__(self, resid: str, links:List[str]=[], mobility_services:List[str]=[]):
        super(Sensor, self).__init__(resid)
        self.mobility_services = frozenset(mobility_services)
        self.links: FrozenSet[str] = frozenset(links)


    def __dump__(self) -> dict:
        return {'ID': self.id, 'MOBILITY_SERVICES': list(self.mobility_services), 'LINKS': list(self.links)}

    @classmethod
    def __load__(cls, data: dict):
        return Sensor(data['ID'], data['LINKS'], data['MOBILITY_SERVICES'])


class MultiModalGraph(object):
    """MultiModalGraph class, it holds the geometry of the network in a GeoGraph and the mobility services in
    a TopoGraph

    Attributes
    ----------
    flow_graph: GeoGraph
        Graph representing the geometry of the network
    mobility_graph: TopoGraph
        Graph representing all the mobility services and their connexions
    sensors: dict
        Dict of reservoirs define on flow_graph
    """
    def __init__(self, nodes:Dict[str, Tuple[float]]={}, links:Dict[str, Tuple[float]]= {}, mobility_services=[]):
        self.flow_graph = GeoGraph()
        self.mobility_graph = ComposedTopoGraph()
        self.sensors = dict()

        self._connexion_services = dict()
        self._mobility_services = dict()

        self.node_referencing = defaultdict(list)

        [self.flow_graph.add_node(nid, pos) for nid, pos in nodes.items()]
        [self.flow_graph.add_link(lid, unid, dnid) for lid, (unid, dnid) in  links.items()]
        [serv.connect_graph(self) for serv in mobility_services]

    def connect_mobility_service(self, lid: str,  upstream_node: str, downstream_node:str, costs={}):
        costs.update({"length":0})
        upstream_service = self.mobility_graph.nodes[upstream_node].mobility_service
        downstream_service = self.mobility_graph.nodes[downstream_node].mobility_service
        assert upstream_service != downstream_service, f"Upstream service must be different from downstream service ({upstream_service})"

        link = TransitLink(lid, upstream_node, downstream_node, costs)
        self.mobility_graph.add_link(link)
        self._connexion_services[(upstream_node, downstream_node)] = lid
        # self._adjacency_services[upstream_service].add(downstream_service)


    def add_sensor(self, sid: str, links: List[str]):
        for lid in links:
            nodes = self.flow_graph._map_lid_nodes[lid]
            self.flow_graph.links[nodes].sensor = sid
        self.sensors[sid] = Sensor(sid, links)

    def get_extremities(self):
        extremities = {nid for nid, neighbors in self.flow_graph._adjacency.items() if len(neighbors) == 1}
        return extremities
