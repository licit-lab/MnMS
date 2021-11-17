from typing import Dict, Tuple, List
from collections import defaultdict

import numpy as np


class Node(object):
    def __init__(self, id, pos):
        self.id = id
        self.pos = np.array(pos)
        self.layers = []


class GeoLink(object):
    def __init__(self, upstream_node, downstream_node):
        self.upstream_node = upstream_node
        self.downstream_node = downstream_node


class TopoLink(object):
    def __init__(self, upstream_node, downstream_node):
        self.upstream_node = upstream_node
        self.downstream_node = downstream_node
        self.costs = dict()
        self.costs['length'] = np.linalg.norm(upstream_node.pos - downstream_node.pos)

        self.reference_geo_link = []


class OrientedGraph(object):
    """Short summary.

    Attributes
    ----------
    nodes : type
        Description of attribute `nodes`.
    edges : type
        Description of attribute `edges`.

    """
    def __init__(self):
        self.nodes: Dict[str, Node] = dict()
        self.edges: Dict[Tuple[str, str], Link] = dict()
        self._adjacency: Dict[str, List[str]] = defaultdict(list)

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node

    def add_link(self, upstream_node: str, downstream_node: str, costs: Dict[str, float]={}):
        l = Link(self.nodes[upstream_node], self.nodes[downstream_node])
        l.costs.update(costs)
        self.edges[(upstream_node, downstream_node)] = l
        self._adjacency[upstream_node].append(downstream_node)

    def get_node_neighbors(self, nodeid: str) -> List[str]:
        return self._adjacency[nodeid]

    def extract_subgraph(self, nodes:set):
        subgraph = OrientedGraph()

        for n in nodes:
            new_node = Node(self.nodes[n].id, self.nodes[n].pos)
            subgraph.add_node(new_node)

        [subgraph.add_link(u_node, d_node, costs=self.edges[(u_node, d_node)].costs) for u_node, d_node in self.edges if u_node in nodes and d_node in nodes]

        return subgraph

class Layer(object):
    def __init__(self, layerid, graph):
        self.id = layerid
        self.nodes = set()
        self._graph = graph
        self._adjacency = dict()

    def add_node(self, node: Node):
        node.layers.append(self.id)
        self.nodes.add(node.id)
        self._graph.add_node(node)

    def add_link(self, upstream_node: str, downstream_node: str, costs: Dict[str, float]={}):
        assert upstream_node in self.nodes
        assert downstream_node in self.nodes
        self._graph.add_link(upstream_node, downstream_node, costs)



class MultiLayerGraph(object):
    def __init__(self):
        self.layers = dict()
        self._connected_layers = dict()
        self.graph = OrientedGraph()

    def create_layer(self, layerid: str) -> Layer:
        g = Layer(layerid, self.graph)
        self.layers[layerid] = g
        return g

    def connect_layer(self, node_1: Node, node_2: Node, costs: Dict[str, float]={}):
        self.graph.add_link(node_1.id, node_2.id, costs)
        self.graph.add_link(node_2.id, node_1.id, costs)

        self._connected_layers[node_1.id] = node_2.layers
        self._connected_layers[node_2.id] = node_1.layers


if __name__ == '__main__':
    g = MultiLayerGraph()

    bus_layer = g.create_layer('Bus')
    car_layer = g.create_layer('Car')

    shared_node = Node('shared_node', [0, 0])
    bus_node1 = Node('bus_node1', [1, 1])
    car_node1 = Node('car_node1', [1, 1])

    bus_layer.add_node(shared_node)
    car_layer.add_node(shared_node)

    bus_layer.add_node(bus_node1)
    car_layer.add_node(car_node1)

    g.connect_layer(bus_node1, car_node1, costs={"time": 12})

    print(shared_node.layers)
    print(g._connected_layers)
