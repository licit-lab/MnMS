from abc import abstractmethod
from collections import defaultdict
from typing import Optional, Dict, List, Type, Callable

from hipop.graph import OrientedGraph

from mnms.graph.road import RoadDescriptor
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.tools.observer import CSVVehicleObserver
from mnms.vehicles.fleet import FleetManager
from mnms.vehicles.veh_type import Vehicle
from mnms.graph.specific_layers import OriginDestinationLayer

import numpy as np

class CostFunctionLayer(object):
    def __init__(self):
        self._costs_functions: Dict[str, Dict[str, Callable]] = defaultdict(dict)

    def add_cost_function(self, mobility_service: str, cost_name: str, cost_function: Callable[[Dict[str, float]], float]):
        self._costs_functions[mobility_service][cost_name] = cost_function


class AbstractLayer(CostFunctionLayer):
    def __init__(self,
                 roads: RoadDescriptor,
                 id: str,
                 veh_type: Type[Vehicle],
                 default_speed: float,
                 services: Optional[List[AbstractMobilityService]] = None,
                 observer: Optional[CSVVehicleObserver] = None):
        """
        The class for implementation of a layer graph

        Args:
            roads: The road object used to construct the graph
            id: The id of the layer
            ml_parent_graph : The multi-layer parent graph
            veh_type: The type of the vehicle on the layer
            default_speed: The default speed of the vehicle on the layer
            services: The services that used the layer
            observer: An observer to write information about the vehicles in the layer
        """
        super(AbstractLayer, self).__init__()
        self._id: str = id

        self.graph: OrientedGraph = OrientedGraph()
        self._parent_graph: OrientedGraph = OrientedGraph()

        self.roads: RoadDescriptor = roads

        self._default_speed: float = default_speed

        self.map_reference_links: Dict[str, List[str]] = dict()
        self.map_reference_nodes: Dict[str, str] = dict()

        # self._costs_functions: Dict[Dict[str, Callable]] = defaultdict(dict)

        self.mobility_services: Dict[str, AbstractMobilityService] = dict()
        self._veh_type: Type[Vehicle] = veh_type

        if services is not None:
            for s in services:
                self.add_mobility_service(s)
                if observer is not None:
                    s.attach_vehicle_observer(observer)

    def add_mobility_service(self, service: AbstractMobilityService):
        service.layer = self
        service.fleet = FleetManager(self._veh_type, service.id)
        self.mobility_services[service.id] = service

    # def add_cost_function(self, mobility_service: str, cost_name: str, cost_function: Callable[[Dict[str, float]], float]):
    #     self._costs_functions[mobility_service][cost_name] = cost_function

    def connect_origindestination(self, odlayer:OriginDestinationLayer, connection_distance: float):
        """
        Connects the origin destination layer to a layer

        Args:
            odlayer: Origin destination layer to connect
            connection_distance: Each node of the origin destination layer is connected to the nodes of the current layer
            within a radius defined by connection_distance (m)
        Return:
            transit_links: List of transit link to add
        """
        transit_links=[]

        assert odlayer is not None

        _norm = np.linalg.norm

        odlayer_nodes = set()
        odlayer_nodes.update(odlayer.origins.keys())
        odlayer_nodes.update(odlayer.destinations.keys())

        graph_nodes = self.graph.nodes
        graph_node_ids = np.array([nid for nid in graph_nodes])
        graph_node_pos = np.array([n.position for n in graph_nodes.values()])

        for nid in odlayer.origins:
            npos = np.array(odlayer.origins[nid])
            dist_nodes = _norm(graph_node_pos - npos, axis=1)
            mask = dist_nodes < connection_distance
            for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                if layer_nid not in odlayer_nodes:
                    lid = f"{nid}_{layer_nid}"
                    transit_links.append({'id': lid,'upstream_node':nid,'downstream_node':layer_nid,'dist':dist})

        for nid in odlayer.destinations:
            npos = np.array(odlayer.destinations[nid])
            dist_nodes = _norm(graph_node_pos - npos, axis=1)
            mask = dist_nodes < connection_distance
            for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                if layer_nid not in odlayer_nodes:
                    lid = f"{layer_nid}_{nid}"
                    transit_links.append({'id': lid, 'upstream_node': layer_nid, 'downstream_node': nid, 'dist': dist})

        return transit_links

    @property
    def default_speed(self):
        return self._default_speed

    @property
    def id(self):
        return self._id

    @property
    def vehicle_type(self):
        return self._veh_type.__name__

    @property
    def parent_graph(self):
        return self._parent_graph

    @parent_graph.setter
    def parent_graph(self, value):
        self._parent_graph = value

    @abstractmethod
    def __dump__(self):
        pass

    @classmethod
    @abstractmethod
    def __load__(cls, data: Dict, roads: RoadDescriptor):
        pass

    def initialize(self):
        pass
