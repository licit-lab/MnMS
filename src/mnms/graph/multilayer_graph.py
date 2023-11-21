from typing import Optional, Dict, List, Callable

from mnms.graph.abstract import AbstractLayer
from mnms.graph.specific_layers import OriginDestinationLayer
from hipop.graph import OrientedGraph, merge_oriented_graph, graph_to_dict
from collections import ChainMap
from mnms.graph.dynamic_space_sharing import DynamicSpaceSharing
from mnms.graph.layers import TransitLayer

import numpy as np
class MultiLayerGraph(object):
    """
    Multi layer graph class

    Attributes:
        graph (OrientedGraph): the graph representation based on HiPOP
        layers (dict): the layers
        odlayer (OriginDestinationLayer): the origin destination layer
        transitlayer (TransitLayer): the transit layer between the layers
        roads (RoadDescriptor): the road descriptor
    """

    def __init__(self,
                 layers:List[AbstractLayer] = [],
                 odlayer:Optional[OriginDestinationLayer] = None,
                 connection_distance:Optional[float] = None):
        """
        Args:
            layers: List of mobility service layer to add to the multilayer graph
            odlayer: Origin destination layer
            connection_distance: Distance to be considered for connecting an origin destination layer node to mobility service layer nodes
        """
        self.graph: OrientedGraph = merge_oriented_graph([l.graph for l in layers])

        for l in layers:
            l.parent_graph = self.graph

        self.layers = dict()

        self.mapping_layer_services = dict()
        self.map_reference_links = ChainMap()

        self.map_linkid_layerid=dict()  # Link and layer mapping

        self.dynamic_space_sharing = DynamicSpaceSharing(self)

        for l in layers:
            self.map_reference_links.maps.append(l.map_reference_links)
            for lid in l.map_reference_links.keys():
                self.map_linkid_layerid[lid]= l.id

        self.odlayer = None
        self.transitlayer = TransitLayer()
        self.roads = layers[0].roads

        for l in layers:
            self.layers[l.id] = l

        if odlayer is not None:
            self.add_origin_destination_layer(odlayer)
            if connection_distance is not None:
                self.connect_origindestination_layers(connection_distance)

    def add_origin_destination_layer(self, odlayer: OriginDestinationLayer):
        self.odlayer = odlayer

        [self.graph.add_node(nid, pos[0], pos[1], odlayer.id) for nid, pos in odlayer.origins.items()]
        [self.graph.add_node(nid, pos[0], pos[1], odlayer.id) for nid, pos  in odlayer.destinations.items()]

    def connect_origindestination_layers(self, connection_distance: float):
        """
        Connects the origin destination layer to the other layers

        Args:
            connection_distance: Each node of the origin destination layer is connected to the nodes of all other layers
            within a radius defined by connection_distance (m)
        """

        for l in self.layers:
            transit_links = self.layers[l].connect_origindestination(self.odlayer, connection_distance)
            for tl in transit_links:
                self.graph.add_link(tl['id'], tl['upstream_node'], tl['downstream_node'], tl['dist'], {"WALK": {'length': tl['dist']}}, "TRANSIT")
                self.map_linkid_layerid[tl['id']] = "TRANSIT"
                # Add the transit link into the transit layer
                up_layer = self.graph.nodes[tl['upstream_node']].label
                down_layer = self.graph.nodes[tl['downstream_node']].label
                self.transitlayer.add_link(tl['id'], up_layer, down_layer)
    def connect_intra_layer(self, layer_id: str, connection_distance: float):
        """
                Connects by a transit link each node of a layer to the others within a predefined radius
                Useful, for example, for a public transport layer to get to another stop

                Args:
                    connection_distance: each node  is connected to the nodes within a radius defined by
                        connection_distance (m)

                Returns:
                    Nothing
                """
        assert self.odlayer is not None
        _norm = np.linalg.norm

        odlayer_nodes = set()
        odlayer_nodes.update(self.odlayer.origins.keys())
        odlayer_nodes.update(self.odlayer.destinations.keys())

        graph_node_ids = np.array([nid for nid in self.graph.nodes])
        graph_node_pos = np.array([n.position for n in self.graph.nodes.values()])

        graph_nodes = self.graph.nodes
        for nid in graph_nodes:
            if nid not in odlayer_nodes:
                node = graph_nodes[nid]
                npos = np.array(node.position)
                dist_nodes = _norm(graph_node_pos-npos, axis=1)
                mask = dist_nodes < connection_distance
                for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                    if layer_nid != nid:
                        if layer_nid not in odlayer_nodes:
                            olayer = self.graph.nodes[nid].label
                            dlayer = self.graph.nodes[layer_nid].label
                            if olayer == layer_id and dlayer == layer_id:
                                lid = f"{nid}_{layer_nid}"
                                self.graph.add_link(lid, nid, layer_nid, dist, {"WALK": {'length': dist}}, "TRANSIT")
                                self.map_linkid_layerid[lid]="TRANSIT"
                                # Add the transit link into the transit layer
                                self.transitlayer.add_link(lid, olayer, dlayer)

    def connect_inter_layers(self, layer_id_list: List[str], connection_distance: float):
        """
                Connect different layers with transit links

                Args:
                    _id: The id of the service
                    veh_capacity: The capacity of the vehicle using this service

                Returns:
                    Nothing
        """

        assert self.odlayer is not None
        _norm = np.linalg.norm

        odlayer_nodes = set()
        odlayer_nodes.update(self.odlayer.origins.keys())
        odlayer_nodes.update(self.odlayer.destinations.keys())

        nodes=graph_to_dict(self.graph)['NODES']

        graph_node_ids = np.array([n['ID'] for n in nodes if n['LABEL'] in layer_id_list])
        graph_node_label = np.array([n['LABEL'] for n in nodes if n['LABEL'] in layer_id_list])
        graph_node_pos = np.array([np.array([n['X'],n['Y']]) for n in nodes if n['LABEL'] in layer_id_list])

        for nid in graph_node_ids:
            if nid not in odlayer_nodes:
                idx=np.where(graph_node_ids==nid)
                npos = graph_node_pos[idx]
                olayer=graph_node_label[idx][0]
                dist_nodes = _norm(graph_node_pos-npos, axis=1)
                mask = dist_nodes < connection_distance
                for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                    if layer_nid != nid:
                        if layer_nid not in odlayer_nodes:
                            idxd = np.where(graph_node_ids == layer_nid)
                            dlayer=graph_node_label[idxd][0]
                            lid = f"{nid}_{layer_nid}"
                            self.graph.add_link(lid, nid, layer_nid, dist, {"WALK": {'length': dist}}, "TRANSIT")
                            self.map_linkid_layerid[lid]="TRANSIT"
                            # Add the transit link into the transit layer
                            self.transitlayer.add_link(lid, olayer, dlayer)

    def construct_layer_service_mapping(self):
        for layer in self.layers.values():
            for service in layer.mobility_services:
                self.mapping_layer_services[service] = layer

    def connect_layers(self, lid: str, upstream: str, downstream: str, length: float, costs: Dict[str, float]):
        if "WALK" not in costs:
            costs = {"WALK": costs}
        self.graph.add_link(lid, upstream, downstream, length, costs, "TRANSIT")
        self.map_linkid_layerid[lid]="TRANSIT"
        # Add the transit link into the transit layer
        link_olayer_id = self.graph.nodes[upstream].label
        link_dlayer_id = self.graph.nodes[downstream].label
        self.transitlayer.add_link(lid, link_olayer_id, link_dlayer_id)

    def initialize_costs(self,walk_speed):

        # initialize costs on links
        link_layers = list()

        for lid, layer in self.layers.items():
            link_layers.append(layer.graph.links)  # only non transit links concerned

        for link in self.graph.links.values():
            costs = {}
            if link.label == "TRANSIT":
                layer = self.transitlayer
                speed = walk_speed
                costs["WALK"] = {"speed": speed,
                                 "travel_time": link.length / speed,
                                 "distance": link.length}
                # NB: travel_time could be defined as a cost_function
                for mservice, cost_functions in layer._costs_functions.items():
                    for cost_name, cost_func in cost_functions.items():
                        costs[mservice][cost_name] = cost_func(self, link, costs)
            else:
                layer = self.layers[link.label]
                speed = layer.default_speed

                link_layer_id = link.label
                for mservice in self.layers[link_layer_id].mobility_services.keys():
                    costs[mservice] = {"speed": speed,
                                       "travel_time": link.length / speed,
                                       "distance": link.length}
                # NB: travel_time could be defined as a cost_function
                for mservice, cost_functions in layer._costs_functions.items():
                    for cost_name, cost_func in cost_functions.items():
                        costs[mservice][cost_name] = cost_func(self, link, costs)

            link.update_costs(costs)

            for links in link_layers: # only non transit links concerned
                layer_link = links.get(link.id, None)
                if layer_link is not None:
                    layer_link.update_costs(costs)

    def add_cost_function(self, layer_id: str, cost_name: str, cost_function: Callable, mobility_service: Optional[str] = None):
        # Retrieve layer
        if layer_id == 'TRANSIT':
            layer = self.transitlayer
            mservices = ["WALK"]
        else:
            layer = self.layers[layer_id]
            mservices = list(layer.mobility_services.keys())

        # Add cost function on layer
        if mobility_service is not None:
            layer.add_cost_function(mobility_service, cost_name, cost_function)
        else:
            for mservice in mservices:
                layer.add_cost_function(mservice, cost_name, cost_function)
