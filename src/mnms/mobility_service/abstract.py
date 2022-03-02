from abc import ABC,abstractmethod
from typing import Type, Tuple, List

from mnms.demand.user import User
from mnms.graph.core import TopoGraph
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
            if self._graph.nodes[dnode].mobility_service == self.id:
                key = (unode, dnode)
                veh_path.append((key, self._graph.links[key].costs['length']))
            else:
                break
        return veh_path

    def share_graph(self, service:"AbstractMobilityService"):
        self._graph = service._graph

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
    def __load__(self, data:dict):
        pass

    @abstractmethod
    def update(self, dt:Dt):
        pass

    @abstractmethod
    def request_vehicle(self, user: "User", drop_node:str) -> Tuple[Dt, str, Vehicle]:
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

