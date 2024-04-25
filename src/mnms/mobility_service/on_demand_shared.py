from collections import deque
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Deque, Any
from queue import PriorityQueue
import sys
import numpy as np
import math

from hipop.shortest_path import dijkstra, compute_path_length

from mnms import create_logger
from mnms.demand import User
from mnms.demand.horizon import AbstractDemandHorizon
from mnms.graph.zone import Zone
from mnms.mobility_service.abstract import AbstractOnDemandMobilityService, compute_path_travel_time, Request
from mnms.mobility_service.interfaces import Depot
from mnms.mobility_service.filters import FilterProtocol, IsWaiting, InRadiusFilter
from mnms.time import Dt, Time
from mnms.tools.exceptions import PathNotFound
from mnms.vehicles.veh_type import Vehicle, VehicleActivity, ActivityType, VehicleActivityStop, VehicleActivityPickup, \
    VehicleActivityServing, VehicleActivityRepositioning
from mnms.tools.cost import create_service_costs
from mnms.tools.geometry import polygon_area, get_bounding_box

log = create_logger(__name__)

@dataclass(order=True)
class PrioritizedItem:
    priority: float
    item: Any=field(compare=False)

@dataclass
class UserInfo:
    request: Request
    initial_distance: float # distance user has traveled when she got matched with this service
    initial_path_distance: float # distance user was supposed to travel with this service when she planned
    traveled_distance: float = field(default=0, init=False) # distance traveler traveled onboard a vehicle of this service

    def __repr__(self):
        return f"UserInfo({self.request.user.id}, {self.initial_distance}, "\
            f"{self.initial_path_distance}, {self.traveled_distance})"

    def update_distance(self):
        """Method that updated the distance traveled by a user onboard a vehicle
        of a service using UserInfo object.
        """
        self.traveled_distance = self.request.user.distance - self.initial_distance

def truncate_plan(user: User, vehicle_plan: List[VehicleActivity]) -> List[VehicleActivity]:
    """Function that truncates a plan from user's pickup if it is in plan, or from
    current activity otherwise, to user's dropoff.

    Args:
        -user: user to target
        -vehicle_plan: plan to truncate

    Retruns:
        -truncate: the truncated plan
    """
    # Truncate plan right till user dropoff
    truncate = []
    valid = False
    for a in vehicle_plan:
        truncate.append(a)
        if a.activity_type is ActivityType.SERVING and a.user.id == user.id:
            valid = True
            break
    if not valid:
        return []
    # Check if user pikcup is in plan
    pu_in_plan = [i for i,a in enumerate(truncate) if a.activity_type is ActivityType.PICKUP and a.user.id == user.id]
    if pu_in_plan:
        # Truncate plan left
        pu_index = pu_in_plan[0]
        truncate = truncate[pu_index+1:]

    return truncate

def get_remaining_distance(veh: Vehicle, plan: List[VehicleActivity]) -> float:
    """Method that computes the remaining distance vehicle has to run to achieve
    the plan.
    """
    flatten_path_link = [p[0] for activity in plan for p in activity.path]
    flatten_path_dist = [p[1] for activity in plan for p in activity.path]
    try:
        # Vehicle has already started to run plan
        index_current_link = flatten_path_link.index(veh.current_link)
        remaining_dist = sum(flatten_path_dist[index_current_link+1:]) + veh.remaining_link_length
    except ValueError:
        # Vehicle should run the whole plan
        remaining_dist = sum(flatten_path_dist)
    return remaining_dist

def path_to_nodes(path) -> List[str]:
    """Method that converts a built path into a list of nodes.

    Args:
        -path: path to convert

    Returns:
        -path_nodes: the converted path
    """
    if len(path) > 0:
        path_nodes = [l[0][0] for l in path] + [path[-1][0][1]]
    else:
        path_nodes = []
    return path_nodes

def get_user_nodes_from_plan(uid: str, plan: List[VehicleActivity]) -> List[str]:
    """Method that deduce the nodes user will go through based on a plan.

    Args:
        -uid: id of the user
        -plan: the plan
    """
    nodes = []
    user_pu_act_ind = [i for i,a in enumerate(plan) if a.user.id == uid and isinstance(a, VehicleActivityPickup)]
    if user_pu_act_ind:
        start = False
        user_pu_act_ind = user_pu_act_ind[0]
    else:
        start = True # User is in the vehicle from the beginning of the plan

    for i, a in enumerate(plan):
        if start:
            nodes.extend(path_to_nodes(a.path)[:-1])
        if i == user_pu_act_ind:
            start = True
        if a.user.id == uid and isinstance(a, VehicleActivityServing):
            nodes.append(a.node)
            break

    return nodes


class OnDemandSharedMobilityService(AbstractOnDemandMobilityService):
    def __init__(self,
                 id: str,
                 veh_capacity: int,
                 dt_matching: int,
                 dt_periodic_maintenance: int,
                 default_waiting_time: float = 0,
                 matching_strategy: str = 'smallest_disutility_vehicle_in_radius_fifo',
                 replanning_strategy: str = 'all_pickups_first_fifo',
                 radius: float = 10000,
                 detour_ratio: float = 1.343):
        """Constructor of an OnDemandSharedMobilityService object.

        Args:
            -id: id of the service
            -veh_capacity: capacity of the vehicles of this service
            -dt_matching: the number of flow time steps elapsed between two calls
             of the matching
            -dt_periodic_maintenance: the number of flow steps elapsed between two
             call of the periodic maintenance
            -default_waiting_time: default estimated waiting time broadcasted to users at
             the moment of their planning, it is applied initially and when there is no
             idle vehicle nor open request
            -matching_strategy: strategy to apply for the matching
            -replanning_strategy: strategy to apply for the replanning (i.e. to
             insert pickup and serving activities in vehicle's plan)
            -radius: radius in meters used by matching strategies
            -detour_ratio: distance on the actual road network to straight line distance
        """
        super(OnDemandSharedMobilityService, self).__init__(id, veh_capacity, dt_matching,
            dt_periodic_maintenance, default_waiting_time=default_waiting_time)
        self.matching_strategy = matching_strategy
        self.replanning_strategy = replanning_strategy
        self.radius = radius
        self.detour_ratio = detour_ratio

        self._users: Dict[str, UserInfo] = dict()
        self._requests_history = []

        self.gnodes = None

    @property
    def users(self):
        return self._users

    @users.setter
    def users(self, d):
        self._users = d

    @property
    def requests_history(self):
        return self._requests_history

    def add_request(self, user: "User", drop_node:str, request_time:Time) -> None:
        """
        Add a new request to the mobility service defined by the user and her drop node.

        Args:
            -user: user object
            -drop_node: drop node id
            -request_time: time at which request is placed
        """
        super(OnDemandSharedMobilityService, self).add_request(user, drop_node, request_time)
        # Save the request in the proper zone to be able to compute request arrival rate
        self._requests_history.append(Request(user, drop_node, request_time))

    def request(self, user: User, drop_node: str) -> Dt:
        """Method that calls the proper strategy to associate a vehicle to a
        requesting user.

        Args:
            -user: user who requested the service
            -drop_node: node where the user would like to be dropped off

        Returns:
            -service_dt: waiting time before pick-up
        """
        if self.matching_strategy == 'smallest_disutility_vehicle_in_radius_fifo':
            return self.request_smallest_disutility_vehicle_in_radius_fifo(user, drop_node)
        else:
            log.error(f'Undefined matching strategy {self.matching_strategy} for {self.id} service...')
            sys.exit(-1)

    def request_smallest_disutility_vehicle_in_radius_fifo(self, user: User, drop_node: str) -> Dt:
        """Among the vehicles currently within a radius around user's pickup node,
        the one leading to the smallest disutility without infringing user's detour
        constraint is chosen.

        Args:
            -user: user who requested the service
            -drop_node: node where the user would like to be dropped off

        Returns:
            -service_dt: waiting time before pick-up
        """
        service_dt = Dt(hours=24)

        ## Get the vehicles currently within radius around user
        vehs = self.get_all_vehicles()
        filter = InRadiusFilter(self.radius)
        mask = filter.get_mask(self.layer, vehs, position=user.position)
        vehs_in_radius = vehs[mask]

        ## Compute disutility of adding user's pickup and dropoff activities
        #  in each vehicle in radius
        candidate_vehicles = PriorityQueue()
        veh_pickup = dict()
        veh_new_plan = dict()
        for veh in vehs_in_radius:
            if self.able_to_serve_new_request(veh):
                activities = [VehicleActivityPickup(node=user.current_node,
                                                    user=user),
                              VehicleActivityServing(node=drop_node,
                                                     user=user)]
                #log.info(f'Add {activities} to {veh.id} plan {veh.activity} - {veh.activities}')
                new_plan = self.replanning(veh, activities)
                pickup_dt = self.estimate_user_pickup_time_at_match(user, new_plan)
                veh_pickup[veh.id] = pickup_dt
                veh_new_plan[veh.id] = new_plan
                disutility = self.compute_disutility(veh, new_plan, user)
                #log.info(f'New plan = {new_plan}, disutility = {disutility}, pickup dt = {pickup_dt}')

                if disutility != float("inf"):
                    candidate_vehicles.put(PrioritizedItem(disutility, veh))

        #log.info(f'Candidate vehs for {user.id} = {candidate_vehicles}')
        if not candidate_vehicles.empty():
            veh = candidate_vehicles.get().item
            service_dt = veh_pickup[veh.id]
            self._cache_request_vehicles[user.id] = veh, veh_new_plan[veh.id]
            #log.info(f'Veh {veh.id} identified for {user.id}')

        return service_dt

    def estimate_user_pickup_time_at_match(self, user: User, plan: List[VehicleActivity]) -> Dt:
        """Method that estimates the time a user will wait before being picked up
        by a vehicle of this service given its plan.

        Args:
            -user: user who requested the service
            -plan: vehicle's plan integrating user's pickup and serving activities

        Returns:
            -pickup_time: the estimated pick-up time
        """
        pickup_time = Dt()
        for a in plan:
            pickup_time += Dt(seconds=compute_path_travel_time(a.path, self.gnodes, self.id))
            if isinstance(a, VehicleActivityPickup) and a.user == user:
                break
        return pickup_time

    def replanning(self, veh: Vehicle, new_activities: List[VehicleActivity]) -> List[VehicleActivity]:
        """Method that inserts new activities in vehicle's plan.

        Args:
            -veh: vehicle which should replan
            -new_activities: the list of activities to insert in vehicle's plan

        Return:
            -new_plan: the new plan which includes the new activities
        """
        if self.replanning_strategy == 'all_pickups_first_fifo':
            return self.replanning_all_pickups_first_fifo(veh, new_activities)
        else:
            log.error(f'Unknown replanning strategy {self.replanning_strategy} for {self.id} service...')
            sys.exit(-1)

    def replanning_all_pickups_first_fifo(self, veh: Vehicle, new_activities: List[VehicleActivity]) -> List[VehicleActivity]:
        """Method that inserts all new pickup activities in the order in which they are
        passed right after the last pickup activity of vehicle's current plan, and all
        serving activities in the order in which they are passed in the end of vehicle's
        current plan.

        Args:
            -veh: vehicle which should replan
            -new_activities: the list of activities to insert in vehicle's plan

        Return:
            -new_plan: the new plan which includes the new activities
        """
        ## Split new activities by type by keeping their order
        new_pu_activities = []
        new_serv_activities = []
        for a in new_activities:
            if isinstance(a, VehicleActivityPickup):
                new_pu_activities.append(a)
            elif isinstance(a, VehicleActivityServing):
                new_serv_activities.append(a)
            else:
                log.error(f'Method replanning_all_pickups_first_fifo does not support '\
                    f'other activities than pickup and serving, found a {type(a).__name__} activity...')
                sys.exit(-1)

        new_plan = [veh.activity.copy()] + [activity.copy() for activity in veh.activities]
        veh_current_node = veh.current_node
        veh_next_node = veh.current_link[1] if (not isinstance(veh.activity, VehicleActivityStop) and veh.current_link is not None) else None
        remaining_first_link_length = veh.remaining_link_length if veh_next_node is not None else None

        if new_pu_activities:
            ## Insert the pickup activities after the last pickup activity of vehicle's current plan
            pu_activities_indices = [i for i,a in enumerate(new_plan) if isinstance(a, VehicleActivityPickup)]
            if pu_activities_indices:
                last_pu_activity_index = pu_activities_indices[-1]
            else:
                last_pu_activity_index = -1 # we will interrupt current activity
            insertion_index =  last_pu_activity_index + 1
            for new_pu_activity in reversed(new_pu_activities):
                new_plan = self.insert_activity_by_index_in_plan(new_plan, new_pu_activity,
                    insertion_index, veh.current_node, forced_next_node=veh_next_node,
                    remaining_first_link_length=remaining_first_link_length)

        if new_serv_activities:
            ## Insert the serving activities at the end of plan
            for new_serv_activity in new_serv_activities:
                new_plan = self.insert_activity_by_index_in_plan(new_plan, new_serv_activity,
                    len(new_plan), veh.current_node, forced_next_node=veh_next_node,
                    remaining_first_link_length=remaining_first_link_length)

        return new_plan

    def insert_activity_by_index_in_plan(self, plan: List[VehicleActivity], activity: VehicleActivity, index: int, start_node: str, forced_next_node: str = None, remaining_first_link_length: float = None) -> List[VehicleActivity]:
        """Method that insert an activity in a plan by index.
        NB: if activity at this index before the insertion is of type VehicleActivityStop
        or VehicleActivityRepositioning, it is removed from the plan.

        Args:
            -plan: plan where to insert the activity
            -activity: activity to insert
            -index: index at which the activity should be inserted
            -start_node: node where plan should start if relevant
            -forced_next_node: node where vehicle should arrive right after start_node
            -remaining_first_link_length: the distance vehicle already has to run between
             start_node and forced_next_node

        Returns:
            -incremented_plan: the plan with the new activity inserted
        """
        next_a = plan[index] if index < len(plan) else None
        prev_a = plan[index-1] if index-1 >= 0 else None
        assert (not isinstance(prev_a, VehicleActivityStop)) and (not isinstance(prev_a, VehicleActivityRepositioning))

        ## Get last node before new activity starts and compute path of the inserted activity
        add_current_node = False
        if prev_a is not None:
            prev_node = prev_a.node
        else:
            if forced_next_node is None:
                prev_node = start_node
            else:
                prev_node = forced_next_node
                add_current_node = True
        if prev_node != activity.node:
            try:
                path, cost = dijkstra(self.graph,
                                      prev_node,
                                      activity.node,
                                      'travel_time',
                                      {self.layer.id: self.id},
                                      {self.layer.id})
            except ValueError as ex:
                log.error(f'HiPOP.Error: {ex}')
                sys.exit(-1)
            if cost == float('inf'):
                raise PathNotFound(prev_node, activity.node)
        else:
            if add_current_node:
                path = [forced_next_node]
            else:
                path = []
            cost = 0
        if add_current_node:
            path = [start_node] + path
        activity.modify_path(self.construct_veh_path(path))
        if add_current_node:
            activity.path[0] = (activity.path[0][0], remaining_first_link_length)
        ## Insert the new activity
        plan.insert(index, activity)

        ## Overwrite first activity path and remaining length on first link if relevant
        if forced_next_node is not None and not add_current_node:
            assert remaining_first_link_length is not None
            found = False if len(plan[0].path) > 0 else True
            for i in range(len(plan[0].path)):
                if plan[0].path[i][0] == (start_node, forced_next_node):
                    first_a_new_path = plan[0].path[i:]
                    first_a_new_path[0] = (first_a_new_path[0][0], remaining_first_link_length)
                    plan[0].modify_path_and_next(first_a_new_path)
                    found = True
                    break
            if not found:
                log.error(f"Cannot find current link {start_node}-{forced_next_node} "\
                    f"in plan's first activity {plan[0]} (remaining_first_link_length={remaining_first_link_length})")
                sys.exit(-1)

        ## Modify path of the next activity consequently or remove activity
        #  if STOP or REPOSITIONING
        if isinstance(next_a, VehicleActivityStop) or isinstance(next_a, VehicleActivityRepositioning):
            del plan[index+1]
            next_a = plan[index+1] if index+1 < len(plan) else None
        if next_a is not None:
            try:
                path, cost = dijkstra(self.graph,
                                      activity.node,
                                      next_a.node,
                                      'travel_time',
                                      {self.layer.id: self.id},
                                      {self.layer.id})
            except ValueError as ex:
                log.error(f'HiPOP.Error: {ex}')
                sys.exit(-1)
            if cost == float('inf'):
                raise PathNotFound(activity.node, next_a.node)
            next_a.modify_path(self.construct_veh_path(path))

        return plan

    def matching(self, request: Request, dt: Dt):
        """Method that effectively matches a user with the identified vehicle of
        this service.

        Args:
            -request: request to be matched
            -dt: flow time step
        """
        user = request.user

        veh, new_plan = self._cache_request_vehicles[user.id]
        veh.activities = deque(new_plan)
        veh.override_current_activity()
        user.set_state_waiting_vehicle(veh)
        immediate_match = len(new_plan) > 1 \
            and new_plan[0].user == request.user and new_plan[0].path == [] \
            and new_plan[1].user == request.user and type(new_plan[1]).__name__ == 'VehicleActivityServing'\
            and self._tcurrent - request.request_time <= dt
        if immediate_match:
            veh.dt_move = self._tcurrent - request.request_time

        ## Update user's and (future) passengers' paths' with regard to this match
        passengers = set([a.user for a in new_plan])
        for passenger in passengers:
            nodes_at_match = get_user_nodes_from_plan(passenger.id, new_plan)
            service_index = passenger.get_mobility_service_index_in_path(self.id)
            service_slice = passenger.path.layers[service_index][1]
            nodes = passenger.path.nodes[service_slice]
            if nodes != nodes_at_match:
                passenger.modify_path_leg(self.id, nodes_at_match)
            if passenger.id == user.id:
                ## Save user's info at matching
                initial_path_dist = compute_path_length(self.graph, nodes)
                self.users[user.id] = UserInfo(request, user.distance, initial_path_dist) # NB: support only one simultaneous req per user

        log.info(f'User {user.id} matched with vehicle {veh.id} of mobility service {self.id} (new plan = {new_plan})')

    def launch_matching(self, new_users, user_flow, decision_model, dt):
        """Method that launches the matching phase.

        Args:
            -new_users: users who have chosen a path but not yet departed
            -user_flow: the UserFlow object of the simulation
            -decision_model: the AbstractDecisionModel object of the simulation
            -dt: time since last call of this method (flow time step)
        """
        super(OnDemandSharedMobilityService, self).launch_matching(new_users, user_flow, decision_model, dt)
        if self._counter_matching == 0:
            # (Re)compute estimated pickup times after this matching phase
            self.update_estimated_pickup_times(dt)

    def step_maintenance(self, dt: Dt):
        """Method that proceeds to the maintenance phase.
        It updates the distances users matched with this service have run onboard
        a vehicle of this service and deletes the information of users who have
        already been dropped off by a vehicle of this service. Also, it computes
        the estimated waiting time(s) for a request in each zone of this service.

        Args:
            -dt: time elapsed since the previous maintenance phase
        """
        self.gnodes = self.graph.nodes

        ## Manage users info
        users_info_to_del = []
        for uid in self.users:
            # Check if user has been dropped off
            user_req = self.users[uid].request
            user_achieved_path = user_req.user.achieved_path
            user_achieved_path_ms = user_req.user.achieved_path_ms
            if self.id in user_achieved_path_ms and user_req.pickup_node in user_achieved_path \
                and user_req.drop_node in user_achieved_path:
                # If so, remove user's info
                users_info_to_del.append(uid)
            else:
                # If not, update distance traveled in user's info
                self.users[uid].update_distance()

        for uid in users_info_to_del:
            del self.users[uid]

        ## (Re)compute estimated pickup times
        self.update_estimated_pickup_times(dt)

    def compute_disutility(self, vehicle: Vehicle, new_plan: List[VehicleActivity], new_user: User):
        """Method that computes the disutility of a new plan for the vehicle compared
        to its current plan. The disutility is the sum of the disutilities for all expected
        passengers, plus eventually the disutility for the new user.

        Args:
            -vehicle: the vehicle for which to compute disutility
            -new_plan: the new plan for which to compute disutility
            -new_user: the new user included in new_plan whose disutility should
             be taken into account

        Returns:
            -total_disutility: the disutility associated to vehicle and new_plan
        """
        ## Gather users whose disutility should be taken into account
        passengers = list(vehicle.passengers.values())
        all_activities = [vehicle.activity] + list(vehicle.activities)
        future_passengers = [a.user for a in all_activities if isinstance(a, VehicleActivityPickup)]
        expected_users = passengers + future_passengers + [new_user]

        ## Compute total disutility
        total_disutility = 0
        for user in expected_users:
            disutility = self.compute_user_disutility(user, vehicle, new_plan)
            total_disutility += disutility

        return total_disutility

    def compute_user_disutility(self, user: User, vehicle: Vehicle, new_plan: List[VehicleActivity]) -> float:
        """Method that computes user's disutility for a new plan compared to vehicle's
        current plan.
        User's disutility is infinite if user's maximum detour ratio is overcome in
        the new plan. Otherwise, it is equal to the additional distance traveled by
        the vehicle in the new plan plan till user's drop off.

        Args:
            -user: user whose disutility should be computed
            -vehicle: the vehicle for which disutility should be computed
            -new_plan: the new plan for which disutility should be computed

        Returns:
            -user_disutility
        """
        # Get the distance user is supposed to ride onboard vehicle in current plan
        current_plan_truncated = truncate_plan(user, [vehicle.activity] + list(vehicle.activities))
        current_remaining_distance = get_remaining_distance(vehicle, current_plan_truncated)

        # Get the distance user is supposed to ride onboard vehicle in new plan
        new_plan_truncated = truncate_plan(user, new_plan)
        new_remaining_distance = get_remaining_distance(vehicle, new_plan_truncated)

        # Deduce user disutility as the marginal distance
        user_disutility = new_remaining_distance - current_remaining_distance

        # Compute the total distance user will travel onboard vehicle in the new plan
        traveled_distance = self.users[user.id].traveled_distance if user.id in self.users else 0
        total_distance = traveled_distance + new_remaining_distance

        # Find back or compute the initial distance user was supposed to travel
        # onboard vehicle of this service
        if user.id in self.users:
            initial_path_distance = self.users[user.id].initial_path_distance
        else:
            service_index = user.get_mobility_service_index_in_path(self.id)
            service_slice = user.path.layers[service_index][1]
            nodes = user.path.nodes[service_slice]
            initial_path_distance = compute_path_length(self.graph, nodes)

        # Deduce detour ratio for the user
        detour_ratio = total_distance / initial_path_distance

        # Check user's max detour ratio constraint
        if detour_ratio > user.max_detour_ratio:
            return float("inf")

        return user_disutility

    def able_to_serve_new_request(self, veh: Vehicle) -> bool:
        """Method that checks if vehicle is able to serve a new request. The feasibility
        depends on the replanning strategy.
        """
        if self.replanning_strategy == 'all_pickups_first_fifo':
            # Vehicle is able to serve a new request if it is not full and has space
            # for a new passenger at the end of the pickup activities of its plan
            if veh.is_full:
                return False
            all_activities = [veh.activity] + list(veh.activities)
            pickups_count = sum([1 for a in all_activities if isinstance(a,VehicleActivityPickup)])
            awaited_nb_passengers = pickups_count + len(veh.passengers)
            if awaited_nb_passengers >= veh.capacity:
                return False
            return True
        else:
            log.error(f'Unknown replanning strategy {self.replanning_strategy} for {self.id} service...')
            sys.exit(-1)

    def update_estimated_pickup_times(self, dt: Dt):
        """Method that computes the estimated waiting time(s) for a request
        in each zone of this service.

        Args:
            -dt: time elapsed since the previous maintenance phase
        """
        glinks = self.graph.links
        # Treat zone per zone when they are defined
        count_links_treated = 0
        for zid, z in self._zones.items():
            count_links_treated += len(z.links)
            # Count the nb of idle vehicles in this zone
            idle_vehs = self.get_idle_vehicles()
            idle_vehs_pos = [veh.position for veh in idle_vehs]
            mask = z.is_inside(idle_vehs_pos)
            idle_vehs_in_z = np.array(idle_vehs)[mask]

            # Count the nb of open requests in this zone
            open_reqs = list(self.user_buffer.values())
            reqs_pos = [req.user.position for req in open_reqs]
            mask = z.is_inside(reqs_pos)
            open_reqs_in_z = np.array(open_reqs)[mask]

            area = polygon_area(z.contour)
            mean_speed = np.mean([glinks[lid].costs[self.id]['speed'] for lid in z.links])
            tau = (self.dt_matching+1) * dt.to_seconds()

            # Oversupply mode
            if (len(idle_vehs_in_z) > len(open_reqs_in_z)) or (len(idle_vehs_in_z) == len(open_reqs_in_z) and len(idle_vehs_in_z) > 0):
                    idle_vehs_density_in_z = len(idle_vehs_in_z) / area
                    w = tau / 2 + z.detour_ratio / (2 * mean_speed * math.sqrt(idle_vehs_density_in_z))
            # Undersupply mode
            elif (len(idle_vehs_in_z) < len(open_reqs_in_z)) or (len(idle_vehs_in_z) == len(open_reqs_in_z) and len(open_reqs_in_z) > 0):
                open_reqs_density_in_z = len(open_reqs_in_z) / area
                # Compute mean requests arrival rate in this zone
                reqs_hist_pos = [self.graph.nodes[req.pickup_node].position for req in self.requests_history]
                mask = z.is_inside(reqs_hist_pos)
                reqs_hist_in_z = np.array(self.requests_history)[mask]
                if len(reqs_hist_in_z) == 0:
                    log.warning(f'There is no request history in zone {zid}, impossible to estimate pickup time there...')
                    continue
                delta_t = (max(reqs_hist_in_z).request_time - min(reqs_hist_in_z).request_time).to_seconds()
                if delta_t == 0:
                    delta_t = dt.to_seconds() # dt is the smallest time step
                reqs_arrival_rate_in_z = len(reqs_hist_in_z) / delta_t
                # Deduce estimates waiting time
                w = len(open_reqs_in_z) / reqs_arrival_rate_in_z - tau / 2 + z.detour_ratio / (mean_speed * math.sqrt(math.pi * open_reqs_density_in_z))
            # No idle vehicle nor open request : apply default waiting time
            else:
                w = self.default_waiting_time
            self._estimated_pickup_times[zid] = w
        # Check that all links of this service's layer have been treated
        if len(self.zones) > 0 and count_links_treated < len(glinks):
            log.warning(f'Incomplete zoning defined for {self.id} service, we compute '\
                'the estimated waiting time on remaining links considering the whole network...')

        # Treat links all together when no zone is defined
        if len(self.zones) == 0 or (len(self.zones) > 0 and count_links_treated < len(glinks)):
            # Count the nb of idle vehicles on the whole network
            idle_vehs = self.get_idle_vehicles()

            # Count the nb of open requests on the whole network
            open_reqs = list(self.user_buffer.values())

            tau = (self.dt_matching+1) * dt.to_seconds()
            bbox = get_bounding_box(None, graph=self.graph)
            area = max(1, (bbox.xmax - bbox.xmin)) * max(1,(bbox.ymax - bbox.ymin)) # max(1,-) for flat networks
            mean_speed = np.mean([glinks[lid].costs[self.id]['speed'] for lid in glinks])
            delta_t = (max(open_reqs).request_time - min(open_reqs).request_time).to_seconds() if open_reqs else np.nan
            if delta_t == 0:
                delta_t = dt.to_seconds() # dt is the smallest time step

            # Oversupply
            if (len(idle_vehs) > len(open_reqs)) or (len(idle_vehs) == len(open_reqs) and len(idle_vehs) > 0):
                idle_vehs_density = len(idle_vehs) / area
                w = tau / 2 + self.detour_ratio / (2 * mean_speed * math.sqrt(idle_vehs_density))
            # Undersupply
            elif (len(idle_vehs) < len(open_reqs)) or (len(idle_vehs) == len(open_reqs) and len(open_reqs) > 0):
                open_reqs_density = len(open_reqs) / area
                # Compute mean requests arrival rate on these links
                reqs_hist = self.requests_history
                assert len(reqs_hist) > 0, f'There is no request history, impossible to estimate pickup time there...'
                delta_t = (max(reqs_hist).request_time - min(reqs_hist).request_time).to_seconds()
                if delta_t == 0:
                    delta_t = dt.to_seconds() # dt is the smallest time step
                reqs_arrival_rate = len(reqs_hist) / delta_t
                w = len(open_reqs) / reqs_arrival_rate - tau / 2 + self.detour_ratio / (mean_speed * math.sqrt(math.pi * open_reqs_density))
            # No idle vehicle nor open request : apply default waiting time
            else:
                w = self.default_waiting_time
            self._estimated_pickup_times['default'] = w

    def __dump__(self) -> dict:
        return {"TYPE": ".".join([OnDemandSharedMobilityService.__module__, OnDemandSharedMobilityService.__name__]),
                "VEH_CAPACITY": self.veh_capacity,
                "DT_MATCHING": self.dt_matching,
                "DT_PERIODIC_MAINTENANCE": self._dt_periodic_maintenance,
                "ID": self.id,
                "DEFAULT_WAITING_TIME": self.default_waiting_time,
                "MATCHING_STRATEGY": self.matching_strategy,
                "REPLANNING_STRATEGY": self.replanning_strategy,
                "RADIUS": self.radius}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data["VEH_CAPACITY"], data["DT_MATCHING"],
            data["DT_PERIODIC_MAINTENANCE"], data['DEFAULT_WAITING_TIME'],
            data['MATCHING_STRATEGY'], data['REPLANNING_STRATEGY'],
            data['RADIUS'])
        return new_obj
