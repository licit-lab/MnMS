from typing import Tuple, List, Dict

from mnms.demand import User
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.time import Dt
from mnms.vehicles.veh_type import VehicleActivityServing, VehicleState, Vehicle


class PersonalMobilityService(AbstractMobilityService):
    def __init__(self, _id: str = 'PersonalVehicle'):
        super(PersonalMobilityService, self).__init__(_id, veh_capacity=1, dt_matching=0, dt_periodic_maintenance=0)

    def request(self, users: Dict[str, Tuple[User, str]]) -> Dict[str, Dt]:
        return {u: Dt() for u in users}

    def matching(self, user: User, drop_node: str):
        upath = list(user.path.nodes)
        upath = upath[upath.index(user._current_node):upath.index(drop_node) + 1]
        veh_path = self._construct_veh_path(upath)
        new_veh = self.fleet.create_vehicle(upath[0],
                                            capacity=self._veh_capacity,
                                            activities=[VehicleActivityServing(node=user.destination,
                                                                               path=veh_path,
                                                                               user=user)])
        if self._observer is not None:
            new_veh.attach(self._observer)

    def step_maintenance(self, dt: Dt):
        for veh in list(self.fleet.vehicles.values()):
            if veh.state is VehicleState.STOP:
                self.fleet.delete_vehicle(veh.id)

    def replanning(self):
        pass

    def rebalancing(self, next_demand: List[User], horizon: List[Vehicle]):
        pass

    def __dump__(self):
        return {"TYPE": ".".join([PersonalMobilityService.__module__, PersonalMobilityService.__name__]),
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'])
        return new_obj
