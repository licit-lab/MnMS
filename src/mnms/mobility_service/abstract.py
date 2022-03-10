from abc import ABC,abstractmethod
from typing import Type, Tuple, List

from mnms.demand.user import User
from mnms.graph.core import TopoGraph
from mnms.graph.shortest_path import Path, astar
from mnms.tools.time import Time, Dt
from mnms.vehicles.fleet import FleetManager
from mnms.vehicles.veh_type import Vehicle


class AbstractMobilityService(ABC):
    def __init__(self, id:str, veh_type:Type[Vehicle], default_speed:float):
        super(AbstractMobilityService, self).__init__()
        self.fleet = FleetManager(veh_type)
        self.id = id
        self.default_speed = default_speed
        self._graph = TopoGraph()

        self._observer = None
        self._tcurrent = None
        self._veh_type = veh_type
        self._graph_is_shared = False

    def set_time(self, time:Time):
        self._tcurrent = time.copy()

    def update_time(self, dt:Dt):
        self._tcurrent = self._tcurrent.add_time(dt)

    def attach_vehicle_observer(self, observer):
        self._observer = observer

    def _construct_veh_path(self, upath: List[str]):
        veh_path = list()
        for i in range(len(upath)-1):
            unode = upath[i]
            dnode = upath[i+1]
            key = (unode, dnode)
            veh_path.append((key, self._graph.links[key].costs['length']))
        return veh_path

    def share_graph(self, service:"AbstractMobilityService"):
        self._graph = service._graph
        self._graph_is_shared = True

    def compute_shortest_path(self, user:User, cost:str, heuristic) -> Path:
        return astar(self._graph, user, cost, heuristic)

    @property
    def graph_is_shared(self):
        return self._graph_is_shared

    @abstractmethod
    def update_costs(self, time: Time):
        pass

    @abstractmethod
    def connect_to_service(self, nid) -> dict:
        pass

    @abstractmethod
    def __dump__(self) -> dict:
        pass

    @classmethod
    @abstractmethod
    def __load__(cls, data:dict):
        pass

    @abstractmethod
    def update(self, dt:Dt):
        pass

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

