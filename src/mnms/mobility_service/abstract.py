from abc import ABC,abstractmethod
from typing import List, Tuple, Optional, Dict
from functools import cached_property

from mnms.demand.horizon import AbstractDemandHorizon
from mnms.demand.user import User
from mnms.tools.cost import create_service_costs
from mnms.time import Time, Dt
from mnms.vehicles.fleet import FleetManager
from mnms.vehicles.veh_type import Vehicle


class AbstractMobilityService(ABC):
    def __init__(self,
                 _id: str,
                 dt_matching: int,
                 veh_capacity: int,
                 demand_horizon: Optional[AbstractDemandHorizon] = None):
        self._id: str = _id
        self.layer: "AbstractLayer" = None
        self._tcurrent: Time = None
        self.fleet: FleetManager = None
        self._observer = None
        self._dt_matching: int = dt_matching
        self._horizon: Optional[AbstractDemandHorizon] = demand_horizon
        self._counter_matching: int = 0
        self._user_buffer: Dict[str, Tuple[User, str]] = dict()
        self._veh_capacity: int = veh_capacity

    def set_time(self, time:Time):
        self._tcurrent = time.copy()

    def update_time(self, dt:Dt):
        self._tcurrent = self._tcurrent.add_time(dt)

    def set_demand_horizon(self, horizon: AbstractDemandHorizon):
        self._horizon = horizon

    @property
    def id(self):
        return self._id

    @property
    def graph(self):
        return self.layer.graph

    @cached_property
    def graph_nodes(self):
        return self.graph.nodes

    def attach_vehicle_observer(self, observer):
        self._observer = observer

    def _construct_veh_path(self, upath: List[str]):
        veh_path = list()
        for i in range(len(upath)-1):
            unode = upath[i]
            dnode = upath[i+1]
            key = (unode, dnode)
            link_length = self.graph_nodes[unode].adj[dnode].length
            veh_path.append((key, link_length))
        return veh_path

    def service_level_costs(self, nodes:List[str]) -> dict:
        """
        Must return a dict of costs representing the cost of the service computed from a path
        Parameters
        ----------
        path

        Returns
        -------

        """
        return create_service_costs()

    def request_vehicle(self, user: "User", drop_node:str) -> None:
        self._user_buffer[user.id] = (user, drop_node)

    def update(self, dt: Dt):
        self.maintenance(dt)
        self._counter_matching += 1

    def launch_matching(self):
        if self._counter_matching == self._dt_matching:
            self._counter_matching = 0
            user_matched = self.matching(self._user_buffer)

            for u in user_matched:
                del self._user_buffer[u]


    @abstractmethod
    def maintenance(self, dt: Dt):
        pass

    @abstractmethod
    def matching(self, users: List[Tuple[User, str]]):
        pass

    @abstractmethod
    def rebalancing(self, next_demand: List[User], stop_veh: List[Vehicle]):
        pass

    @abstractmethod
    def replaning(self):
        pass

    @classmethod
    @abstractmethod
    def __load__(cls, data):
        pass

    @abstractmethod
    def __dump__(self) -> dict:
        pass



