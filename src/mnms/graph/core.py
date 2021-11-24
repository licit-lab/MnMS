from typing import Dict, Tuple, List, Union
from collections import defaultdict
from abc import ABC, abstractmethod
import numpy as np

from mnms.graph.reservoir import Reservoir
from mnms.log import logger

class TopoNode(object):
    def __init__(self, id, ref_node=None):
        self.id = id
        self.reference_node = ref_node

    def __repr__(self):
        return f"TopoNode(id={self.id}, ref_node={self.reference_node})"

class GeoNode(object):
    def __init__(self, id, pos):
        self.id = id
        self.pos = np.array(pos)

    def __repr__(self):
        return f"GeoNode(id={self.id}, pos={self.pos})"

class TopoLink(object):
    def __init__(self, lid, upstream_node, downstream_node, costs=None, reference_links=None, reference_lane_ids=None,
                 mobility_service=None):
        self.id = lid
        self.upstream_node = upstream_node
        self.downstream_node = downstream_node
        self.costs = costs if costs is not None else {}
        self.reference_links = reference_links if reference_links is not None else []
        self.reference_lane_ids = []
        self.mobility_service = mobility_service

        if reference_links is not None:
            if reference_lane_ids is None:
                self.reference_lane_ids = [0]*len(reference_links)
            else:
                self.reference_lane_ids = reference_lane_ids

    def __repr__(self):
        return f"TopoLink(id={self.id}, upstream={self.upstream_node}, downstream={self.downstream_node})"

class GeoLink(object):
    def __init__(self, lid, upstream_node, downstream_node, nb_lane=1):
        self.id = lid
        self.upstream_node = upstream_node
        self.downstream_node = downstream_node
        self.nb_lane = nb_lane
        self.reservoir = None

    def __repr__(self):
        return f"GeoLink(id={self.id}, upstream={self.upstream_node}, downstream={self.downstream_node})"

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
        self.links: Dict[Tuple[str, str], Union[TopoLink, GeoLink]] = dict()
        self._adjacency: Dict[str, List[str]] = defaultdict(set)
        self._map_lid_nodes: Dict[str, Tuple[str, str]] = dict()

    @abstractmethod
    def add_node(self, *args, **kwargs) -> None:
        raise NotImplementedError

    @abstractmethod
    def add_link(self, *args, **kwargs) -> None:
        raise NotImplementedError

    def get_node_neighbors(self, nodeid: str) -> List[str]:
        return self._adjacency[nodeid]

    @abstractmethod
    def extract_subgraph(self, nodes:set):
        raise NotImplementedError

    @property
    def nb_nodes(self):
        return len(self.nodes)

    @property
    def nb_links(self):
        return len(self.links)


class TopoGraph(OrientedGraph):
    def add_node(self, nodeid: str, ref_node:str=None) -> None:
        assert nodeid not in self.nodes

        node = TopoNode(nodeid, ref_node)
        self.nodes[node.id] = node

    def add_link(self, lid, upstream_node, downstream_node, costs, reference_links=None, reference_lane_ids=None,
                 mobility_service=None) -> None:
        assert (upstream_node, downstream_node) not in self.links, f"Nodes {upstream_node}, {downstream_node} already in graph"
        assert lid not in self._map_lid_nodes, f"Link id {lid} already exist"

        link = TopoLink(lid, upstream_node, downstream_node, costs, reference_links, reference_lane_ids, mobility_service)
        self.links[(upstream_node, downstream_node)]= link
        self._map_lid_nodes[lid] = (upstream_node, downstream_node)
        self._adjacency[upstream_node].add(downstream_node)

    def extract_subgraph(self, nodes:set):
        subgraph = self.__class__()
        for n in nodes:
            subgraph.add_node(n)

        [subgraph.add_link(self.links[(u_node, d_node)].id, u_node, d_node, self.links[(u_node, d_node)].costs) for u_node, d_node in self.links if u_node in nodes and d_node in nodes]

        return subgraph


class GeoGraph(OrientedGraph):
    def add_node(self, nodeid: str, pos: List[float]) -> None:
        assert nodeid not in self.nodes

        node = GeoNode(nodeid, pos)
        self.nodes[node.id] = node

    def add_link(self, lid, upstream_node: str, downstream_node: str, nb_lane:int=1) -> None:
        assert (upstream_node, downstream_node) not in self.links

        link = GeoLink(lid, upstream_node, downstream_node, nb_lane=nb_lane)
        self.links[(upstream_node, downstream_node)] = link
        self._map_lid_nodes[lid] = (upstream_node, downstream_node)
        self._adjacency[upstream_node].add(downstream_node)

    def extract_subgraph(self, nodes:set):
        subgraph = self.__class__()
        for n in nodes:
            subgraph.add_node(n, self.nodes[n].pos)

        [subgraph.add_link(self.links[(u_node, d_node)].id, u_node, d_node) for u_node, d_node in self.links if u_node in nodes and d_node in nodes]

        return subgraph

class MobilityGraph(object):
    def __init__(self, mid: str, topograph: TopoGraph):
        self._graph = topograph
        self.nodes = set()
        self.links = dict()
        self.id = mid

    def add_node(self, id, ref_node=None):
        self.nodes.add(id)
        self._graph.add_node(self.id+"_"+id, ref_node)

    def add_link(self, lid, upstream_node: str, downstream_node: str, costs:Dict[str, float], reference_links=None, reference_lane_ids=None):
        self.links[(upstream_node, downstream_node)] = lid
        self._graph.add_link(lid, self.id+"_"+upstream_node, self.id+"_"+downstream_node, costs, reference_links, reference_lane_ids, self.id)

    def set_cost(self, cost_name:str, default_value:float):
        for unode, dnode in self.links.keys():
            self._graph.links[(self.id+"_"+unode, self.id+"_"+dnode)].costs[cost_name] = default_value


class MultiModalGraph(object):
    def __init__(self):
        self.flow_graph = GeoGraph()
        self.mobility_graph = TopoGraph()
        self.reservoirs = dict()

        self._connexion_services = defaultdict(set)
        self._adjacency_services = defaultdict(set)
        self._mobility_services = dict()

    def add_mobility_service(self, id):
        assert id not in self._mobility_services
        self._mobility_services[id] = MobilityGraph(id, self.mobility_graph)
        return self._mobility_services[id]


    def add_full_recovery_service(self, servid):
        name_serv = servid
        new_service = self.add_mobility_service(name_serv)
        [new_service.add_node(n) for n in self.flow_graph.nodes]
        [new_service.add_link('_'.join([name_serv, unode, dnode]), unode, dnode, {}, reference_links=[link.id]) for (unode, dnode), link in self.flow_graph.links.items()]


    def connect_mobility_service(self, upstream_service, downstream_service, nodeid, costs={}):
        costs.update({"length":0})
        self.mobility_graph.add_link("_".join([upstream_service, downstream_service, nodeid]),
                                     upstream_service+"_"+nodeid,
                                     downstream_service+"_"+nodeid,
                                     costs)
        self._connexion_services[(upstream_service, downstream_service)].add(nodeid)
        self._adjacency_services[upstream_service].add(downstream_service)


    def add_reservoir(self, resid: str, links: List[str]):
        for lid in links:
            nodes = self.flow_graph._map_lid_nodes[lid]
            self.flow_graph.links[nodes].reservoir = resid
        self.reservoirs[resid] = Reservoir(resid, links)

if __name__ == '__main__':
    from mnms.log import set_log_level, LOGLEVEL
    set_log_level(LOGLEVEL.DEBUG)
    mmgraph = MultiModalGraph()

    mmgraph.flow_graph.add_node('0', [0, 0])
    mmgraph.flow_graph.add_node('1', [1, 0])
    mmgraph.flow_graph.add_node('2', [1, 1])
    mmgraph.flow_graph.add_node('3', [0, 1])

    mmgraph.flow_graph.add_link('0_1', '0', '1')
    mmgraph.flow_graph.add_link('1_0', '1', '0')

    mmgraph.flow_graph.add_link('1_2', '1', '2')
    mmgraph.flow_graph.add_link('2_1', '2', '1')

    mmgraph.flow_graph.add_link('2_3', '2', '3')
    mmgraph.flow_graph.add_link('3_2', '3', '2')

    mmgraph.flow_graph.add_link('3_1', '3', '1')
    mmgraph.flow_graph.add_link('1_3', '1', '3')

    bus_service = mmgraph.add_mobility_service('Bus')
    car_service = mmgraph.add_mobility_service('Car')
    uber_service = mmgraph.add_mobility_service('Uber')

    bus_service.add_node('0', '0')
    bus_service.add_node('1')
    bus_service.add_node('2')

    bus_service.add_link('BUS_0_1', '0', '1', {'time': 5.5}, reference_links=['0_1'])
    bus_service.add_link('BUS_1_2', '1', '2', {'time': 50.5}, reference_links=['1_2'])
    bus_service.add_link('BUS_0_2', '0', '2', {'time': 10.3}, reference_links=[])

    car_service.add_node('0')
    car_service.add_node('1')
    car_service.add_node('2')
    car_service.add_node('3')

    car_service.add_link('CAR_0_1', '0', '1', {'time': 15.1}, reference_links=['0_1'])
    car_service.add_link('CAR_1_0', '1', '0', {'time': 5.1}, reference_links=['1_0'])
    car_service.add_link('CAR_1_2', '1', '2', {'time': 7.1}, reference_links=['1_2'])
    car_service.add_link('CAR_2_1', '2', '1', {'time': 5.1}, reference_links=['2_1'])
    car_service.add_link('CAR_2_3', '2', '3', {'time': 5.1}, reference_links=['2_3'])
    car_service.add_link('CAR_3_2', '3', '2', {'time': 5.1}, reference_links=['3_2'])
    car_service.add_link('CAR_3_1', '3', '1', {'time': 5.1}, reference_links=['3_1'])
    car_service.add_link('CAR_1_3', '1', '3', {'time': 5.1}, reference_links=['1_3'])


    uber_service.add_node('0')
    uber_service.add_node('1')

    uber_service.add_link('UBER_0_1', '0', '1', {'time': 1}, reference_links=['0_1'])

    mmgraph.connect_mobility_service('Bus', 'Car', '0', {'time': 2})
    mmgraph.connect_mobility_service('Car', 'Bus', '0', {'time': 2})
    mmgraph.connect_mobility_service('Bus', 'Uber', '0', {'time': 4})
    mmgraph.connect_mobility_service('Uber', 'Bus', '0', {'time': 2})
    mmgraph.connect_mobility_service('Uber', 'Car', '0', {'time': 2})
    mmgraph.connect_mobility_service('Car', 'Uber', '0', {'time': 2})


    mmgraph.connect_mobility_service('Bus', 'Car', '1', {'time': 2})
    mmgraph.connect_mobility_service('Car', 'Bus', '1', {'time': 2})
    mmgraph.connect_mobility_service('Bus', 'Uber', '1', {'time': 4})
    mmgraph.connect_mobility_service('Uber', 'Bus', '1', {'time': 2})
    mmgraph.connect_mobility_service('Uber', 'Car', '1', {'time': 2})
    mmgraph.connect_mobility_service('Car', 'Uber', '1', {'time': 2})


    mmgraph.connect_mobility_service('Bus', 'Car', '2', {'time': 2});
    mmgraph.connect_mobility_service('Car', 'Bus', '2', {'time': 2})
    mmgraph.connect_mobility_service('Bus', 'Uber', '2', {'time': 4})
    mmgraph.connect_mobility_service('Uber', 'Bus', '2', {'time': 2})
    mmgraph.connect_mobility_service('Uber', 'Car', '2', {'time': 2})
    mmgraph.connect_mobility_service('Car', 'Uber', '2', {'time': 2})

    print(mmgraph.shortest_path('0', '2', cost='time'))