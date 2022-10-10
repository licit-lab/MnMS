from abc import ABC, abstractmethod, ABCMeta
from typing import List, Tuple, Optional, Dict
from functools import cached_property

from mnms.log import create_logger
from mnms.demand.horizon import AbstractDemandHorizon
from mnms.demand.user import User
from mnms.tools.cost import create_service_costs
from mnms.time import Time, Dt
from mnms.vehicles.fleet import FleetManager
from mnms.vehicles.veh_type import Vehicle, VehicleActivity

log = create_logger(__name__)


class AbstractMobilityService(ABC):
    def __init__(self,
                 _id: str,
                 veh_capacity: int,
                 dt_matching: int,
                 dt_periodic_maintenance: int):
        self._id: str = _id
        self.layer: "AbstractLayer" = None
        self._tcurrent: Optional[Time] = None
        self.fleet: Optional[FleetManager] = None
        self._observer: Optional = None
        self._user_buffer: Dict[str, Tuple[User, str]] = dict()
        self._veh_capacity: int = veh_capacity

        self._counter_maintenance: int = 0
        self._dt_periodic_maintenance: int = dt_periodic_maintenance

        self._counter_matching: int = 0
        self._dt_matching: int = dt_matching

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

    def _construct_veh_path(self, upath: List[str]):
        veh_path = list()
        for i in range(len(upath)-1):
            unode = upath[i]
            dnode = upath[i+1]
            key = (unode, dnode)
            link_length = self.graph.nodes[unode].adj[dnode].length
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
        self.step_maintenance(dt)

        if self._counter_maintenance == self._dt_periodic_maintenance:
            self._counter_maintenance = 0
            self.periodic_maintenance(dt)
        else:
            self._counter_maintenance += 1

    def launch_matching(self):
        refuse_user = list()

        if self._counter_matching == self._dt_matching:
            self._counter_matching = 0
            negotiation = self.request(self._user_buffer)

            for uid, service_dt in negotiation.items():
                user, drop_node = self._user_buffer[uid]
                if user.pickup_dt[self.id] > service_dt:
                    self.matching(user, drop_node)
                else:
                    log.info(f"{uid} refused {self.id} offer (predicted pickup time too long)")
                    user.set_state_stop()
                    user.notify(self._tcurrent)
                    refuse_user.append(user)

            self._user_buffer = dict()
        else:
            self._counter_matching += 1

        return refuse_user

    def periodic_maintenance(self, dt: Dt):
        """
        This method is called every n step to perform maintenance
        Args:
            dt:

        Returns:
            None
        """
        pass

    def step_maintenance(self, dt: Dt):
        pass

    @abstractmethod
    def matching(self, user: User, drop_node: str):
        pass

    @abstractmethod
    def request(self, users: Dict[str, Tuple[User, str]]) -> Dict[str, Dt]:
        pass

    def replanning(self, veh: Vehicle, new_activities: List[VehicleActivity]) -> List[VehicleActivity]:
        pass

    @classmethod
    @abstractmethod
    def __load__(cls, data):
        pass

    @abstractmethod
    def __dump__(self) -> dict:
        pass


class AbstractOnDemandMobilityService(AbstractMobilityService, metaclass=ABCMeta):
    def __init__(self,
                 _id: str,
                 dt_matching: int,
                 dt_rebalancing: int,
                 veh_capacity: int,
                 horizon: AbstractDemandHorizon):
        super(AbstractOnDemandMobilityService, self).__init__(_id, veh_capacity, dt_matching, dt_rebalancing)
        self._horizon: AbstractDemandHorizon = horizon

    @abstractmethod
    def rebalancing(self, next_demand: List[User], horizon: Dt):
        pass

    def update(self, dt: Dt):
        self.step_maintenance(dt)

        if self._counter_maintenance == self._dt_periodic_maintenance:
            self._counter_maintenance = 0
            self.periodic_maintenance(dt)

            next_demand = self._horizon.get(self._tcurrent.add_time(dt))
            self.rebalancing(next_demand, self._horizon.dt)
        else:
            self._counter_maintenance += 1

