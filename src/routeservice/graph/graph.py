from typing import Dict, Tuple, List, Union
from collections import defaultdict
from abc import ABC, abstractmethod
import numpy as np


class TopoNode(object):
    def __init__(self, id):
        self.id = id

class GeoNode(TopoNode):
    def __init__(self, id, pos):
        super(GeoNode, self).__init__(id)
        self.pos = np.array(pos)


class TopoLink(object):
    def __init__(self, lid, upstream_node, downstream_node, costs=None, reference_links=None):
        self.id = lid
        self.upstream_node = upstream_node
        self.downstream_node = downstream_node
        self.costs = costs if costs is not None else {}
        self.reference_links = reference_links if reference_links is not None else []


class GeoLink(object):
    def __init__(self, lid, upstream_node, downstream_node):
        self.id = lid
        self.upstream_node = upstream_node
        self.downstream_node = downstream_node


class OrientedGraph(ABC):
    """Short summary.

    Attributes
    ----------
    nodes : type
        Description of attribute `nodes`.
    links : type
        Description of attribute `edges`.

    """
    def __init__(self):
        self.nodes: Dict[str, Union[TopoLink, GeoLink]] = dict()
        self.links: Dict[Tuple[str, str], List[Union[TopoLink, GeoLink]]] = defaultdict(list)
        self._adjacency: Dict[str, List[str]] = defaultdict(set)

    @abstractmethod
    def add_node(self, *args, **kwargs) -> None:
        raise NotImplementedError

    @abstractmethod
    def add_link(self, *args, **kwargs) -> None:
        raise NotImplementedError

    def get_node_neighbors(self, nodeid: str) -> List[str]:
        return self._adjacency[nodeid]

    def extract_subgraph(self, nodes:set):
        subgraph = OrientedGraph()

        for n in nodes:
            new_node = Node(self.nodes[n].id, self.nodes[n].pos)
            subgraph.add_node(new_node)

        [subgraph.add_link(u_node, d_node, costs=self.links[(u_node, d_node)].costs) for u_node, d_node in self.links if u_node in nodes and d_node in nodes]

        return subgraph

    @property
    def nb_nodes(self):
        return len(self.nodes)

    @property
    def nb_links(self):
        return len(self.links)


class TopoGraph(OrientedGraph):
    def add_node(self, nodeid: str) -> None:
        node = TopoNode(nodeid)
        self.nodes[node.id] = node

    def add_link(self, lid, upstream_node, downstream_node, costs, reference_links=None) -> None:
        link = TopoLink(lid, upstream_node, downstream_node, costs, reference_links)
        self.links[(upstream_node, downstream_node)].append(link)
        self._adjacency[upstream_node].add(downstream_node)


class GeoGraph(OrientedGraph):
    def add_node(self, nodeid: str, pos: List[float]) -> None:
        node = GeoNode(nodeid, pos)
        self.nodes[node.id] = node

    def add_link(self, lid, upstream_node: str, downstream_node: str) -> None:
        link = GeoLink(lid, upstream_node, downstream_node)
        self.links[(upstream_node, downstream_node)].append(link)
        self._adjacency[upstream_node].add(downstream_node)

class MobilityService(object):
    def __init__(self, id: str, topograph: TopoGraph):
        self._graph = topograph
        self.nodes = []
        self.links = dict()

    def add_node(self, id):
        self.nodes.append(id)
        self._graph.add_node(id)

    def add_link(self, lid, upstream_node: str, downstream_node: str, costs:Dict[str, float], reference_links=None):
        self.links[(upstream_node, downstream_node)] = lid
        self._graph.add_link(lid, upstream_node, downstream_node, costs, reference_links)


class MultiModalGraph(object):
    def __init__(self):
        self.flow_graph = GeoGraph()
        self.mobility_graph = TopoGraph()

        self._mobility_services = dict()

    def add_mobility_service(self, id):
        self._mobility_services[id] = MobilityService(id, self.mobility_graph)
        return self._mobility_services[id]




if __name__ == '__main__':
    mmgraph = MultiModalGraph()

    mmgraph.flow_graph.add_node('0', [0,0])
    mmgraph.flow_graph.add_node('1', [1,0])
    mmgraph.flow_graph.add_node('2', [1,1])
    mmgraph.flow_graph.add_node('3', [0,1])

    mmgraph.flow_graph.add_link('0', '1')
    mmgraph.flow_graph.add_link('1', '0')

    mmgraph.flow_graph.add_link('1', '2')
    mmgraph.flow_graph.add_link('2', '1')

    mmgraph.flow_graph.add_link('2', '3')
    mmgraph.flow_graph.add_link('3', '2')

    mmgraph.flow_graph.add_link('3', '1')
    mmgraph.flow_graph.add_link('1', '3')

    bus_service = mmgraph.add_mobility_service('Bus')
    car_service = mmgraph.add_mobility_service('Car')

    bus_service.add_node('0')
    bus_service.add_node('1')
    bus_service.add_link('0', '3', {'time': 10})
    bus_service.add_link('3', '0', {'time': 10})

    car_service.add_node('0')
    car_service.add_node('1')
    car_service.add_node('2')
    car_service.add_node('3')
    car_service.add_link('0', '1', {'time': 5.1})
    car_service.add_link('1', '0', {'time': 5.1})
    car_service.add_link('1', '2', {'time': 5.1})
    car_service.add_link('2', '1', {'time': 5.1})
    car_service.add_link('2', '3', {'time': 5.1})
    car_service.add_link('3', '2', {'time': 5.1})
    car_service.add_link('3', '1', {'time': 5.1})
    car_service.add_link('1', '3', {'time': 5.1})