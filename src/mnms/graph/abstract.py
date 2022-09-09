from abc import abstractmethod
from typing import Optional, Dict, List, Type

from hipop.graph import OrientedGraph

from mnms.graph.road import RoadDescriptor
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.tools.observer import CSVVehicleObserver
from mnms.vehicles.fleet import FleetManager
from mnms.vehicles.veh_type import Vehicle, Car


class AbstractLayer(object):
    def __init__(self,
                 roads: RoadDescriptor,
                 id: str,
                 veh_type: Type[Vehicle],
                 default_speed: float,
                 services: Optional[List[AbstractMobilityService]] = None,
                 observer: Optional[CSVVehicleObserver] = None):
        """
        The base class for implementation of a layer graph

        Args:
            roads: The road object used to construct the graph
            id: The id of the layer
            veh_type: The type of the vehicle on the layer
            default_speed: The default speed of the vehicle on the layer
            services: The services that used the layer
            observer: An observer to write information about the vehicles in the layer
        """
        self._id: str = id
        self.graph: OrientedGraph = OrientedGraph()
        self._roaddb: RoadDescriptor = roads
        self._roaddb._layers[id] = self

        self._default_speed: float = default_speed

        self.map_reference_links: Dict[str, List[str]] = dict()
        self.map_reference_nodes: Dict[str, str] = dict()

        self.mobility_services: Dict[str, AbstractMobilityService] = dict()
        self._veh_type: Type[Vehicle] = veh_type

        if services is not None:
            for s in services:
                self.add_mobility_service(s)
                if observer is not None:
                    s.attach_vehicle_observer(observer)

    def add_mobility_service(self, service: AbstractMobilityService):
        service.layer = self
        service.fleet = FleetManager(self._veh_type)
        self.mobility_services[service.id] = service

    @property
    def default_speed(self):
        return self._default_speed

    @property
    def id(self):
        return self._id

    @abstractmethod
    def __dump__(self):
        pass

    @classmethod
    @abstractmethod
    def __load__(cls, data: Dict, roads: RoadDescriptor):
        pass

    def initialize(self):
        pass
