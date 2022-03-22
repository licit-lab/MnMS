from abc import ABC,abstractmethod
from typing import Type, List, Dict

from mnms.demand.user import User
from mnms.graph.core import TopoGraph
from mnms.graph.shortest_path import Path, astar
from mnms.tools.containers import CostDict
from mnms.tools.time import Time, Dt
from mnms.vehicles.fleet import FleetManager
from mnms.vehicles.veh_type import Vehicle


class AbstractMobilityGraphLayer(ABC):
    def __init__(self,
                 id:str,
                 veh_type:Type[Vehicle],
                 default_speed:float,
                 services:List["AbstractMobilityService"]=None,
                 observer=None):
        self.id = id
        self.default_speed = default_speed
        self.mobility_services = dict()
        self.graph = TopoGraph()
        self._veh_type = veh_type

        if services is not None:
            for s in services:
                self.add_mobility_service(s)
                if observer is not None:
                    s.attach_vehicle_observer(observer)

    def add_mobility_service(self, service:"AbstractMobilityService"):
        service.layer = self
        service.fleet = FleetManager(self._veh_type)
        self.mobility_services[service.id] = service

    def compute_shortest_path(self, user:User, cost:str, heuristic) -> Path:
        return astar(self.graph,
                     user.origin,
                     user.destination,
                     cost,
                     None,
                     heuristic)

    @abstractmethod
    def update_costs(self, time: Time):
        pass

    @abstractmethod
    def __dump__(self) -> dict:
        pass

    @classmethod
    @abstractmethod
    def __load__(cls, data:dict):
        pass

    @abstractmethod
    def connect_to_layer(self, nid) -> dict:
        pass


class AbstractMobilityService(ABC):
    def __init__(self, id):
        self._id: str = id
        self.layer: AbstractMobilityGraphLayer = None
        self._tcurrent: Time = None
        self.fleet: FleetManager = None
        self._observer = None

    def set_time(self, time:Time):
        self._tcurrent = time.copy()

    def update_time(self, dt:Dt):
        self._tcurrent = self._tcurrent.add_time(dt)

    @property
    def id(self):
        return self._id

    @property
    def graph(self):
        return self.layer.graph

    def attach_vehicle_observer(self, observer):
        self._observer = observer

    @abstractmethod
    def request_vehicle(self, user: "User", drop_node:str) -> None:
        """This method must be implemented by any subclass of AbstractMobilityService.
        It must found a vehicle and call the take_next_user of the vehicle on the user.

        Parameters
        ----------
        user: User

        Returns
        -------
        None

        """
        pass

    @abstractmethod
    def update(self, dt:Dt):
        pass

    def _construct_veh_path(self, upath: List[str]):
        veh_path = list()
        for i in range(len(upath)-1):
            unode = upath[i]
            dnode = upath[i+1]
            key = (unode, dnode)
            veh_path.append((key, self.graph.links[key].costs['length']))
        return veh_path

    def service_level_costs(self, nodes:List[str]) -> CostDict:
        """
        Must return a dict of costs representing the cost of the service computed from a path
        Parameters
        ----------
        path

        Returns
        -------

        """
        return CostDict(waiting_time=0,
                        environmental=0,
                        currency=0)

