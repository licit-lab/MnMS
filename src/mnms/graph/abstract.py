from abc import abstractmethod
from typing import Optional, Dict, List, Type

from hipop.graph import OrientedGraph

from mnms.graph.road import RoadDataBase
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.vehicles.fleet import FleetManager
from mnms.vehicles.veh_type import Vehicle, Car


class AbstractLayer(object):
    def __init__(self,
                 id: str,
                 roaddb: RoadDataBase,
                 veh_type: Type[Vehicle],
                 default_speed: float,
                 services: Optional[List[AbstractMobilityService]] = None,
                 observer: Optional = None):
        self._id = id
        self.graph = OrientedGraph()
        self._roaddb = roaddb
        self._roaddb._layers[id] = self

        self._default_speed = default_speed

        self.map_reference_links = dict()
        self.map_reference_nodes = dict()

        self.mobility_services = dict()
        self._veh_type = veh_type

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
    def __load__(cls, data: Dict, roaddb: RoadDataBase):
        pass

    def initialize(self):
        pass
