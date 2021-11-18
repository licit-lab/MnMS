from typing import Dict, Tuple, List, Union
from collections import defaultdict
from abc import ABC, abstractmethod
import numpy as np

from routeservice.graph.algorithms.shortest_path import dijkstra
from routeservice.log import logger

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
        self.links: Dict[Tuple[str, str], Union[TopoLink, GeoLink]] = dict()
        self._adjacency: Dict[str, List[str]] = defaultdict(set)

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
    def add_node(self, nodeid: str) -> None:
        node = TopoNode(nodeid)
        self.nodes[node.id] = node

    def add_link(self, lid, upstream_node, downstream_node, costs, reference_links=None) -> None:
        link = TopoLink(lid, upstream_node, downstream_node, costs, reference_links)
        self.links[(upstream_node, downstream_node)]= link
        self._adjacency[upstream_node].add(downstream_node)

    def extract_subgraph(self, nodes:set):
        subgraph = self.__class__()
        for n in nodes:
            subgraph.add_node(n)

        [subgraph.add_link(self.links[(u_node, d_node)].id, u_node, d_node, self.links[(u_node, d_node)].costs) for u_node, d_node in self.links if u_node in nodes and d_node in nodes]

        return subgraph


class GeoGraph(OrientedGraph):
    def add_node(self, nodeid: str, pos: List[float]) -> None:
        node = GeoNode(nodeid, pos)
        self.nodes[node.id] = node

    def add_link(self, lid, upstream_node: str, downstream_node: str) -> None:
        link = GeoLink(lid, upstream_node, downstream_node)
        self.links[(upstream_node, downstream_node)] = link
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
        self.nodes = []
        self.links = dict()
        self.id = mid

    def add_node(self, id):
        self.nodes.append(id)
        self._graph.add_node(self.id+"_"+id)

    def add_link(self, lid, upstream_node: str, downstream_node: str, costs:Dict[str, float], reference_links=None):
        self.links[(upstream_node, downstream_node)] = lid
        self._graph.add_link(lid, self.id+"_"+upstream_node, self.id+"_"+downstream_node, costs, reference_links)


class MultiModalGraph(object):
    def __init__(self):
        self.flow_graph = GeoGraph()
        self.mobility_graph = TopoGraph()

        self._mobility_services = dict()

    def add_mobility_service(self, id):
        assert id not in self._mobility_services
        self._mobility_services[id] = MobilityGraph(id, self.mobility_graph)
        return self._mobility_services[id]

    def connect_mobility_service(self, upstream_service, downstream_service, nodeid, costs={}):
        self.mobility_graph.add_link("_".join([upstream_service, downstream_service, nodeid]),
                                     upstream_service+"_"+nodeid,
                                     downstream_service+"_"+nodeid,
                                     costs)

    def shortest_path(self, origin, dest, cost):

        # Create artificial nodes

        start_nodes = [name+'_'+origin for name, service in self._mobility_services.items() if origin in service.nodes]
        end_nodes = [name+'_'+dest for name, service in self._mobility_services.items() if dest in service.nodes]

        start_node = f"START_{origin}_{dest}"
        end_node = f"END_{origin}_{dest}"
        logger.debug(f"Create artitificial nodes: {start_node}, {end_node}")


        self.mobility_graph.add_node(start_node)
        self.mobility_graph.add_node(end_node)

        logger.debug(f"Create start artitificial links with: {start_nodes}")
        for n in start_nodes:
            self.mobility_graph.add_link(start_node+'_'+n, start_node, n, {cost:0})

        logger.debug(f"Create end artitificial links with: {end_nodes}")
        for n in end_nodes:
            self.mobility_graph.add_link(n+'_'+end_node, n, end_node, {cost:0})

        # Compute paths
        logger.debug(f"Compute path")
        cost, path = dijkstra(self.mobility_graph, start_node, end_node, cost)

        # Clean the graph from artificial nodes

        logger.debug(f"Clean graph")
        del self.mobility_graph.nodes[start_node]
        del self.mobility_graph.nodes[end_node]
        del self.mobility_graph._adjacency[start_node]


        for n in start_nodes:
            del self.mobility_graph.links[(start_node, n)]

        for n in end_nodes:
            del self.mobility_graph.links[(n, end_node)]
            self.mobility_graph._adjacency[n].remove(end_node)

        del path[0]
        del path[-1]

        return cost, tuple(path)


if __name__ == '__main__':
    from routeservice.log import set_log_level, LOGLEVEL
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

    bus_service.add_node('0')
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