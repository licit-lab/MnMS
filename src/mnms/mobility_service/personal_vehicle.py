from typing import Tuple, List, Dict

from mnms.demand import User
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.time import Dt
from mnms.vehicles.veh_type import VehicleActivityServing, ActivityType, Vehicle, VehicleActivity
from mnms.tools.cost import create_service_costs

class PersonalMobilityService(AbstractMobilityService):
    def __init__(self, _id: str = 'PersonalVehicle'):
        super(PersonalMobilityService, self).__init__(_id, veh_capacity=1,dt_matching=0,dt_periodic_maintenance=0)

    def step_maintenance(self, dt: Dt):
        for veh in list(self.fleet.vehicles.values()):
            if veh.activity_type is ActivityType.STOP:
                self.fleet.delete_vehicle(veh.id)

    def periodic_maintenance(self, dt: Dt):
        pass

    def request(self, user: User, drop_node: str) -> Dt:
        return Dt()

    def matching(self, user: User, drop_node: str):
        upath = list(user.path.nodes)
        upath = upath[upath.index(user._current_node):upath.index(drop_node) + 1]       # why +1 ?
        veh_path = self.construct_veh_path(upath)
        new_veh = self.fleet.create_vehicle(upath[0],
                                            capacity=self._veh_capacity,
                                            activities=[VehicleActivityServing(node=upath[-1],
                                                                               path=veh_path,
                                                                               user=user)])

        if self._observer is not None:
            new_veh.attach(self._observer)

    def replanning(self, veh: Vehicle, new_activities: List[VehicleActivity]) -> List[VehicleActivity]:
        pass

    def rebalancing(self, next_demand: List[User], horizon: List[Vehicle]):
        pass

    def service_level_costs(self, nodes: List[str]) -> dict:
        return create_service_costs()

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'])
        return new_obj

    def __dump__(self):
        return {"TYPE": ".".join([PersonalMobilityService.__module__, PersonalMobilityService.__name__]),
                "ID": self.id}
