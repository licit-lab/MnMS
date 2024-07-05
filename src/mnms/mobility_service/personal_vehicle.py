from typing import Tuple, List, Dict

from mnms.demand import User
from mnms.demand.user import UserState
from mnms.mobility_service.abstract import AbstractMobilityService, Request
from mnms.time import Dt
from mnms.vehicles.veh_type import VehicleActivityServing, ActivityType, Vehicle, VehicleActivity
from mnms.tools.cost import create_service_costs

class PersonalMobilityService(AbstractMobilityService):
    def __init__(self, id: str = 'PersonalVehicle'):
        super(PersonalMobilityService, self).__init__(id, veh_capacity=1, dt_matching=0, dt_periodic_maintenance=0)

    def is_personal(self):
        return True

    def step_maintenance(self, dt: Dt):
        """Method that proceeds to the maintenance phase. For PersonalMobilityService,
        it consists in deleting the vehicles of users who already arrived at their
        destination.

        Args:
            -dt: time elapsed since the previous maintenance phase
        """
        for veh in list(self.fleet.vehicles.values()):
            if veh.activity_type is ActivityType.STOP:
                if veh.last_dropped_off_user is None or (veh.last_dropped_off_user is not None and veh.last_dropped_off_user.state == UserState.ARRIVED):
                    self.fleet.delete_vehicle(veh.id)

    def periodic_maintenance(self, dt: Dt):
        pass

    def request(self, user: User, drop_node: str) -> Dt:
        """Method that returns the expected pick-up time.

        Args:
            -user: user who requested the service
            -drop_node: node where user would like to be droppped off

        Returns:
            -pickup_time: expected time for user to be picked up
        """
        pickup_time = Dt()
        return pickup_time

    def matching(self, request: Request, dt: Dt):
        """Method that proceeds to the matching of a user with a personal vehicle.

        Args:
            -request: the request to match
            -dt: the flow time step
        """
        user = request.user
        drop_node = request.drop_node
        upath = list(user.path.nodes)
        upath = upath[user.get_current_node_index():user.get_node_index_in_path(drop_node) + 1]
        veh_path = self.construct_veh_path(upath)
        # Check if user has already used her personal vehicle
        if self.id in user.personal_vehicles:
            # If so, match her with her own vehicle
            veh = user.personal_vehicles[self.id]
            assert veh.activity_type is ActivityType.STOP, f'Personal vehicle of user {user.id} is not stopped...'
            assert veh.current_node == upath[0], f'User {user.id} tried to take her personal vehcile back at the wrong node ({veh.current_node} != {upath[0]})'
            activities = [VehicleActivityServing(node=upath[-1],
                                                 path=veh_path,
                                                 user=user)]
            veh.add_activities(activities)
            veh.activity.is_done = True
            # For personal vehicle, this is always an immediate match because
            # dt_matching is null, so take into account effective remaining
            # duration to move during the current flow step
            veh.dt_move = self._tcurrent - request.request_time
        else:
            # If not, create a new personal vehicle
            new_veh = self.fleet.create_vehicle(upath[0],
                                            capacity=self._veh_capacity,
                                            activities=[VehicleActivityServing(node=upath[-1],
                                                                               path=veh_path,
                                                                               user=user)])
            user.add_personal_vehicle(self.id, new_veh)
            if self._observer is not None:
                new_veh.attach(self._observer)
            # Take into account effective remaining duration to move during the
            # current flow step
            new_veh.dt_move = self._tcurrent - request.request_time if self._tcurrent is not None else None

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
