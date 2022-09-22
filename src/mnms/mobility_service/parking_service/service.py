from collections import deque
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Deque
from queue import PriorityQueue

import numpy as np
from hipop.shortest_path import dijkstra, compute_path_length

from mnms import create_logger
from mnms.demand import User
from mnms.demand.horizon import AbstractDemandHorizon
from mnms.graph.zone import Zone
from mnms.mobility_service.abstract import AbstractOnDemandMobilityService
from mnms.mobility_service.parking_service.depot import Depot
from mnms.mobility_service.parking_service.filters import FilterProtocol, IsWaiting, InRadiusFilter
from mnms.time import Dt, Time
from mnms.tools.exceptions import PathNotFound
from mnms.vehicles.veh_type import Vehicle, VehicleActivity, VehicleState, VehicleActivityStop, VehicleActivityPickup, \
    VehicleActivityServing

log = create_logger(__name__)

@dataclass
class UserInfo:
    user: User
    initial_distance: float
    initial_path_distance: float
    traveled_distance: float = field(default=0, init=False)

    def update_distance(self):
        self.traveled_distance = self.user.distance - self.initial_distance


def pre_compute_feasibility(vehicle: Vehicle) -> bool:
    if vehicle.state is VehicleState.PICKUP or vehicle.is_full:
        return False
    else:
        return True


# def compute_disutility(veh: Vehicle, new_plan: List[VehicleActivity],  new_user: Optional[User]) -> float:
#     pass


def truncate_plan(user: User, vehicleplan: List[VehicleActivity]) -> List[VehicleActivity]:
    truncate = []
    for act in vehicleplan:
        truncate.append(act)
        if act.state is VehicleState.SERVING and act.user.id == user.id:
            return truncate


def get_discount() -> float:
    return 0


def get_remaining_distance(veh: Vehicle, plan: List[VehicleActivity]) -> float:
    # user = plan[-1].user
    # distance = sum([sum([path[1] for path in act.path]) for act in plan]) + vehicle.remaining_link_length
    # if user.id in self.users:
    #     distance -= self.users[user.id].traveled_distance
    # return distance

    flatten_path_link = [p[0] for activity in plan for p in activity.path]
    flatten_path_dist = [p[1] for activity in plan for p in activity.path]
    index_current_link = flatten_path_link.index(veh.current_link)
    remaining_dist = sum(flatten_path_dist[index_current_link+1:]) + veh.remaining_link_length

    return remaining_dist


class ParkingService(AbstractOnDemandMobilityService):
    def __init__(self,
                 _id: str,
                 dt_matching: int,
                 dt_rebalancing: int,
                 veh_capacity: int,
                 horizon: AbstractDemandHorizon,
                 vehicle_filter: FilterProtocol = None):
        super(ParkingService, self).__init__(_id, veh_capacity, dt_matching, dt_rebalancing, horizon)

        self._cache_request_vehicles: Dict[str, Tuple[Vehicle, List[VehicleActivity]]] = dict()
        self._vehicle_filter = IsWaiting() & InRadiusFilter(100) if vehicle_filter is None else vehicle_filter
        self._replanning_strategy = None
        self.include_all_user_disutility = False

        self.depots: Dict[str, Depot] = dict()

        self.users: Dict[str, UserInfo] = dict()

    def add_depot(self, _id: str, node: str, capacity: int, zone: Zone, fill: bool = True):
        new_depot = Depot(_id, node, capacity, zone.contour)
        self.depots[_id] = new_depot
        if fill:
            for _ in range(capacity):
                veh = self.create_waiting_vehicle(node)
                new_depot.add_vehicle(veh, Time())

    def create_waiting_vehicle(self, node: str):
        new_veh = self.fleet.create_vehicle(node=node,
                                            capacity=self._veh_capacity,
                                            activities=[VehicleActivityStop(node=node)])
        new_veh._position = self.graph.nodes[node].position
        if self._observer is not None:
            new_veh.attach(self._observer)
        return new_veh

    def set_vehicle_filter(self, veh_filter: FilterProtocol):
        self._vehicle_filter = veh_filter

    def set_replanning_strategy(self, strategy):
        self._replanning_strategy = strategy

    def rebalancing(self, next_demand: List[User], horizon: Dt):
        pass

    def replanning(self, veh: Vehicle, new_activities: List[VehicleActivity]) -> Tuple[List[VehicleActivity], Dt]:
        new_plan = [veh.activity.copy()] + [activity.copy() for activity in veh.activities]
        pickup_activity = new_activities[0]
        serving_activity = new_activities[1]
        user = pickup_activity.user

        if veh.state is not VehicleState.STOP:
            veh_next_node = veh.current_link[1]
            pickup_path, cost_pickup = dijkstra(self.graph, veh_next_node, user.current_node, 'travel_time',
                                                {self.layer.id})

            if cost_pickup == float('inf'):
                raise PathNotFound(veh_next_node, user.current_node)

            # first_link = veh.activity.path[0]
            pickup_path = [veh.current_link[0]] + pickup_path
            pickup_activity.modify_path(self._construct_veh_path(pickup_path))
            # pickup_activity.path.insert(0, first_link)
            next(pickup_activity.iter_path)


            current_activity_serving = new_plan[0]
            serving_path_current, cost = dijkstra(self.graph,
                                                  user.current_node,
                                                  current_activity_serving.node,
                                                  'travel_time',
                                                  {self.layer.id})

            if cost == float('inf'):
                raise PathNotFound(user.current_node, current_activity_serving.node)

            current_activity_serving.modify_path(self._construct_veh_path(serving_path_current))

            last_activity = new_plan[-1]
            last_node = last_activity.node

            serving_path_next, cost = dijkstra(self.graph,
                                               last_node,
                                               serving_activity.node,
                                               'travel_time',
                                               {self.layer.id})

            if cost == float('inf'):
                raise PathNotFound(current_activity_serving.node, serving_activity.node)

            serving_activity.modify_path(self._construct_veh_path(serving_path_next))

            new_plan.insert(0, pickup_activity)
            new_plan.append(serving_activity)

        else:
            pickup_path, cost_pickup = dijkstra(self.graph, veh._current_node, user.current_node, 'travel_time',
                                                {self.layer.id})

            if cost_pickup == float('inf'):
                raise PathNotFound(veh._current_node, user.current_node)

            pickup_activity.modify_path(self._construct_veh_path(pickup_path))

            last_activity = veh.activities[-1] if veh.activities else veh.activity
            last_node = last_activity.node
            serving_path, cost = dijkstra(self.graph, last_node, serving_activity.node, 'travel_time', {self.layer.id})

            if cost == float('inf'):
                raise PathNotFound(veh._current_node, user.current_node)

            serving_path = self._construct_veh_path(serving_path)
            serving_activity.path = serving_path
            serving_activity.reset_path_iterator()

            # replacing current serving activity
            current_activity = new_plan[0]
            new_plan[0] = pickup_activity
            new_plan.append(serving_activity)

        return new_plan, Dt(seconds=cost_pickup)

    def matching(self, users: Dict[str, Tuple[User, str]]):
        for uid, (user, drop_node) in users.items():
            veh, new_plan = self._cache_request_vehicles[uid]
            veh.activities = deque(new_plan)
            veh.override_current_activity()
            user.set_state_waiting_vehicle()

            parking_service_index = user.path.mobility_services.index(self.id)
            parking_service_slice = user.path.layers[parking_service_index][1]
            nodes = user.path.nodes[parking_service_slice]
            initial_path_dist = compute_path_length(self.graph, nodes)

            self.users[uid] = UserInfo(user, user.distance, initial_path_dist)

    def request(self, users: Dict[str, Tuple[User, str]]) -> Dict[str, Dt]:
        user_matched = dict()
        all_vehicles = np.array(list(self.fleet.vehicles.values()))
        for uid, (user, drop_node) in users.items():
            mask = self._vehicle_filter.get_mask(self.layer, all_vehicles, user.position, list(self.depots.values()))
            vehicles = all_vehicles[mask]
            candidate_vehicles = PriorityQueue()
            upath = list(user.path.nodes)
            veh_pickup = dict()
            veh_new_plan = dict()
            for veh in vehicles:
                if pre_compute_feasibility(veh):
                    activities = [VehicleActivityPickup(node=user.current_node,
                                                        user=user),
                                  VehicleActivityServing(node=drop_node,
                                                         user=user)]
                    new_plan, pickup_dt = self.replanning(veh, activities)
                    veh_pickup[veh.id] = pickup_dt
                    veh_new_plan[veh.id] = new_plan
                    disutility = self.quality_disutility(veh, new_plan, user if self.include_all_user_disutility else None)

                    if disutility != float("inf"):
                        candidate_vehicles.put((disutility, veh))

            if not candidate_vehicles.empty():
                _, veh = candidate_vehicles.get()
                user_matched[uid] = veh_pickup[veh.id]
                self._cache_request_vehicles[uid] = veh, veh_new_plan[veh.id]

        return user_matched

    def step_maintenance(self, dt: Dt):
        self._cache_request_vehicles: Dict[str, Tuple[Vehicle, List[VehicleActivity]]] = dict()
        for uid in self.users:
            self.users[uid].update_distance()

    def quality_disutility(self, vehicle: Vehicle, new_plan: List[VehicleActivity], new_user: Optional[User]):
        total_disutility = 0

        users = list(vehicle.passenger.values())
        if new_user is not None:
            users.append(new_user)

        for user in users:
            disutility = self.get_disutility(user, vehicle, new_plan)
            total_disutility += disutility

        return total_disutility

    def get_disutility(self, user: User, vehicle: Vehicle, new_plan: List[VehicleActivity]) -> float:
        marginal_cost, detour_ratio = self.get_cost(user, vehicle, new_plan)

        if detour_ratio > user.parameters["max_detour_ratio"]:
            return float("inf")
        return marginal_cost

    def get_cost(self, user: User, vehicle: Vehicle, new_plan: List[VehicleActivity]) -> Tuple[float, float]:
        current_plan_truncated = truncate_plan(user, [vehicle.activity] + list(vehicle.activities))
        current_remaining_distance = get_remaining_distance(vehicle, current_plan_truncated)
        new_plan_truncated = truncate_plan(user, new_plan)
        new_remaining_distance = get_remaining_distance(vehicle, new_plan_truncated)

        marginal_cost = user.parameters["distance_value"] * (new_remaining_distance - current_remaining_distance) - get_discount()
        traveled_distance = self.users[user.id].traveled_distance if user.id in self.users else 0

        total_distance = traveled_distance + new_remaining_distance

        if user.id in self.users:
            initial_path_distance = self.users[user.id].initial_path_distance
        else:
            parking_service_index = user.path.mobility_services.index(self.id)
            parking_service_slice = user.path.layers[parking_service_index][1]
            nodes = user.path.nodes[parking_service_slice]
            initial_path_distance = compute_path_length(self.graph, nodes)
        detour_ratio = total_distance / initial_path_distance

        return marginal_cost, detour_ratio

    def __load__(cls, data):
        pass

    def __dump__(self) -> dict:
        pass