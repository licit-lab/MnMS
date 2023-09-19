from abc import ABC, abstractmethod, ABCMeta
from typing import List, Tuple, Optional, Dict
from mnms.time import Time, Dt
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.log import create_logger
from mnms.vehicles.veh_type import Vehicle, VehicleActivity
from mnms.demand.user import User
from mnms.tools.observer import TimeDependentSubject

log = create_logger(__name__)

class Station(TimeDependentSubject):

    def __init__(self,
                 _id: str,
                 node: str,
                 capacity: int,
                 free_floating: bool,
                 initial_occupancy: int):

        self._id = _id
        self.node = node
        self.capacity = capacity
        self.free_floating = free_floating

        self.occupancy = initial_occupancy


class OnVehicleSharingMobilityService(AbstractMobilityService):

    def __init__(self,
                 _id: str,
                 dt_matching: int,
                 dt_step_maintenance: int = 0):
        super(OnVehicleSharingMobilityService, self).__init__(_id, 1, dt_matching, dt_step_maintenance)

    def step_maintenance(self, dt: Dt):
        pass

    def periodic_maintenance(self, dt: Dt):
        pass

    def request(self, user: User, drop_node: str) -> Dt:
        pass

    def matching(self, user: User, drop_node: str):
        pass

    def replanning(self, veh: Vehicle, new_activities: List[VehicleActivity]) -> List[VehicleActivity]:
        pass

    def rebalancing(self, next_demand: List[User], horizon: Dt):
        pass

    def service_level_costs(self, nodes: List[str]) -> dict:
        pass

    def __load__(cls, data):
        pass

    def __dump__(self) -> dict:
        pass