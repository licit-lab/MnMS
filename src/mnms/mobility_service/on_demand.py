from typing import Tuple, Dict, List

import numpy as np
from scipy.optimize import linear_sum_assignment
import multiprocessing
import sys

from hipop.shortest_path import dijkstra, parallel_dijkstra

from mnms import create_logger
from mnms.demand import User
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.time import Dt
from mnms.tools.exceptions import PathNotFound
from mnms.vehicles.veh_type import ActivityType, VehicleActivityServing, VehicleActivityStop, \
    VehicleActivityPickup, VehicleActivityRepositioning, Vehicle, VehicleActivity
from mnms.tools.cost import create_service_costs

log = create_logger(__name__)


def compute_path_travel_time(path, graph, ms_id):
    tt = 0
    for leg in path:
        leg_link = graph.nodes[leg[0][0]].adj[leg[0][1]]
        tt += leg_link.costs[ms_id]['travel_time']
    return tt

class OnDemandMobilityService(AbstractMobilityService):

    def __init__(self,
                 id: str,
                 dt_matching: int,
                 dt_periodic_maintenance: int = 0,
                 matching_strategy: str='nearest_idle_vehicle_in_radius_fifo',
                 radius: float = 10000):
        super(OnDemandMobilityService, self).__init__(id, veh_capacity=1, dt_matching=dt_matching,
            dt_periodic_maintenance=dt_periodic_maintenance)

        self.gnodes = dict()
        self._matching_strategy = matching_strategy
        self._radius = radius

    @property
    def matching_strategy(self):
        return self._matching_strategy

    @property
    def radius(self):
        return self._radius

    def create_waiting_vehicle(self, node: str):
        """Method to create a vehicle at a certain node of the layer on which this
        mobility service runs.

        Args:
            -node: node at which the vehicle should be created
        """
        assert node in self.graph.nodes
        new_veh = self.fleet.create_vehicle(node,
                                            capacity=self._veh_capacity,
                                            activities=[VehicleActivityStop(node=node)])
        new_veh.set_position(self.graph.nodes[node].position)

        if self._observer is not None:
            new_veh.attach(self._observer)

    def step_maintenance(self, dt: Dt):
        """Method that proceeds to the maintenance phase. It only updates the dictionnary
        of nodes of the graph on which this mobility service runs. TODO: check if this
        is really needed...

        Args:
            -dt: time elapsed since the previous maintenance phase
        """
        self.gnodes = self.graph.nodes

    def periodic_maintenance(self, dt: Dt):
        pass

    def launch_matching(self, new_users, user_flow, decision_model):
        """
        Method that launches the matching phase.

        Args:
            -new_users: users who have chosen a path but not yet departed
            -user_flow: the UserFlow object of the simulation
            -decision_model: the AbstractDecisionModel object of the simulation
        """
        if self._counter_matching == self._dt_matching:
            # Trigger a matching phase
            self._counter_matching = 0
            if self.matching_strategy in ['nearest_idle_vehicle_in_radius_fifo', 'nearest_vehicle_in_radius_fifo']:
                self.launch_matching_fifo()
            elif self.matching_strategy in ['nearest_idle_vehicle_in_radius_batched', 'nearest_vehicle_in_radius_batched']:
                self.launch_matching_batch()
            else:
                log.error(f'Matching strategy {self.matching_strategy} unknown for {self.id} mobility service')
                sys.exit(-1)
        else:
            # Do not tirgger a matching phase
            self._counter_matching += 1

    def launch_matching_fifo(self):
        """Method that launches the matching phase by treating the requests one by
        one in  order of arrival.
        """
        reqs = list(self._user_buffer.values())
        sorted_reqs = sorted(reqs)
        for req in sorted_reqs:
            user = req.user
            drop_node = req.drop_node
            if self.matching_strategy == 'nearest_idle_vehicle_in_radius_fifo':
                service_dt = self.request_nearest_idle_vehicle_in_radius_fifo(user, drop_node)
            elif self.matching_strategy == 'nearest_vehicle_in_radius_fifo':
                service_dt = self.request_nearest_vehicle_in_radius_fifo(user, drop_node)
            else:
                log.error(f'Matching strategy {self.matching_strategy} unknown for {self.id} mobility service')
                sys.exit(-1)
            # Check pick-up time proposition compared with user waiting tolerance
            if user.pickup_dt[self.id] > service_dt:
                # Match user with vehicle
                self.matching(user, drop_node)
                # Remove user from list of users waiting to be matched
                self.cancel_request(user.id)
            else:
                log.info(f"{user.id} refused {self.id} offer (predicted pickup time ({service_dt}) is too long, wait for better proposition...")
            self._cache_request_vehicles = dict()

    def launch_matching_batch(self):
        """Method that launches the matching phase by treating the requests jointly.
        """
        ### Get the batches of requests and considered vehicles
        reqs = list(self._user_buffer.values())
        if self.matching_strategy == 'nearest_idle_vehicle_in_radius_batched':
            vehs = [veh for veh in self.fleet.vehicles.values() if (veh.activity_type in [ActivityType.STOP, ActivityType.REPOSITIONING]) \
                and (not veh.activities)]
        elif self.matching_strategy == 'nearest_vehicle_in_radius_batched':
            vehs = list(self.fleet.vehicles.values())
        else:
            log.error(f'Matching strategy {self.matching_strategy} unknown for {self.id} mobility service')
            sys.exit(-1)
        vehs = np.array(vehs)

        ### Compute the pickup times matrix (for all req-veh pairs)
        inf = 10e8 # will be applied when veh is out of request's radius or service time out of user's tolerance
        pickup_times_matrix = np.full((len(reqs), len(vehs)), inf)
        veh_paths_matrix = np.full((len(reqs), len(vehs)), None)

        ## Gathers params for calling Dijkstra in parallel once
        ridxs = []
        vidxs = []
        origins = []
        destinations = []
        for ridx, req in enumerate(reqs):
            # Search for the vehicles close to the user (within radius)
            vehs_pos = np.array([v.position for v in vehs])
            dist_vector = np.linalg.norm(vehs_pos - req.user.position, axis=1)
            nearest_vehs_indices = dist_vector <= self.radius # radius in meters
            nearest_vehs = vehs[nearest_vehs_indices]
            nearest_vehs_indices = list(np.where(nearest_vehs_indices)[0])

            # Compute estimated pickup time for the vehicles nearby
            for vidx, veh in zip(nearest_vehs_indices, nearest_vehs):
                veh_last_node = veh.activity.node if not veh.activities else \
                        veh.activities[-1].node
                ridxs.append(ridx)
                vidxs.append(vidx)
                origins.append(veh_last_node)
                destinations.append(req.user.current_node)

        ## Call Dijkstra once
        paths = parallel_dijkstra(self.graph,
                                  origins,
                                  destinations,
                                  [{self.layer.id: self.id}]*len(origins),
                                  'travel_time',
                                  multiprocessing.cpu_count(),
                                  [{self.layer.id}]*len(origins))

        ## Parse outputs and complete the pickup times and veh paths matrices
        for i in range(len(paths)):
            ridx = ridxs[i]
            req = reqs[ridx]
            vidx = vidxs[i]
            veh = vehs[vidx]
            veh_path, tt = paths[i]
            # If vehicle cannot reach user, skip and consider next vehicle
            if tt == float('inf'):
                continue
            service_dt = Dt(seconds=tt)
            if veh.activity is not None and veh.activity.activity_type is not ActivityType.STOP:
                veh_curr_act_path_nodes = veh.path_to_nodes(veh.activity.path)
                veh_curr_node_ind_in_path = veh_curr_act_path_nodes.index(veh.current_node) # NB: works only when an acticity path does not contain several times the same node
                service_dt += Dt(seconds=compute_path_travel_time(veh.activity.path[veh_curr_node_ind_in_path+1:], self.graph, self.id))
                current_link = self.graph.nodes[veh.current_node].adj[veh_curr_act_path_nodes[veh_curr_node_ind_in_path+1]]
                service_dt += Dt(seconds=veh.remaining_link_length / current_link.costs[self.id]['speed'])
            for a in veh.activities:
                service_dt += Dt(seconds=compute_path_travel_time(a.path, self.graph, self.id))
            # Apply user's waiting tolerance
            if service_dt < req.user.pickup_dt[self.id]:
                pickup_times_matrix[ridx][vidx] = service_dt.to_seconds()
                veh_paths_matrix[ridx][vidx] = veh_path

        ### Solve the minimum total pickup time matching problem
        row_ind, col_ind = linear_sum_assignment(pickup_times_matrix)

        ### Parse outputs and proceed to the matches when relevant
        for i in range(len(row_ind)):
            req_ind = row_ind[i]
            req = reqs[req_ind]
            veh_ind = col_ind[i]
            veh = vehs[veh_ind]
            if pickup_times_matrix[req_ind][veh_ind] < inf:
                veh_path = veh_paths_matrix[req_ind][veh_ind]
                self._cache_request_vehicles[req.user.id] = veh, veh_path
                self.matching(req.user, req.drop_node)
                self.cancel_request(req.user.id)
                self._cache_request_vehicles = dict()

    def request_nearest_idle_vehicle_in_radius_fifo(self, user: User, drop_node: str) -> Dt:
        """The nearest (in time) idle vehicle located within a certain radius around the
        desired pickup point at the end of its plan is matched with the user. If no
        idle vehicle is within the specified radius, returns an infinite waiting time.

        Args:
            -user: user requesting a ride
            -drop_node: node where user would like to be dropped off

        Returns:
            -service_dt: waiting time before pick-up
        """
        # Get all idle vehicles of the fleet
        idle_vehs = np.array([veh for veh in self.fleet.vehicles.values() if (veh.activity_type in [ActivityType.STOP, ActivityType.REPOSITIONING]) \
            and (not veh.activities)])
        if len(idle_vehs) == 0:
            # There is no idle vehicle in the fleet, match is not possible
            return Dt(hours=24)

        # Search for the idle vehicles close to the user (within radius)
        vehs_pos = np.array([v.position for v in idle_vehs])
        dist_vector = np.linalg.norm(vehs_pos - user.position, axis=1)
        nearest_vehs_indices = dist_vector <= self.radius
        nearest_vehs = idle_vehs[nearest_vehs_indices]
        if len(nearest_vehs) == 0:
            # There is no vehicle surrounding the user, match is not possible
            return Dt(hours=24)

        # Compute service time for the idle vehs in radius
        candidates = []
        for veh in nearest_vehs:
            veh_node = veh.current_node
            veh_path, tt = dijkstra(self.graph, veh_node, user.current_node, 'travel_time', {self.layer.id: self.id}, {self.layer.id})
            if tt == float('inf'):
                # This vehicle cannot reach user, skip and consider next vehicle
                continue
            service_dt = Dt(seconds=tt)
            candidates.append((veh, service_dt, veh_path))

        # Select the veh with the smallest service time
        if candidates:
            candidates.sort(key=lambda x:x[1])
            self._cache_request_vehicles[user.id] = candidates[0][0], candidates[0][2]
        else:
            return Dt(hours=24)

        return candidates[0][1]

    def request_nearest_vehicle_in_radius_fifo(self, user: User, drop_node: str) -> Dt:
        """The nearest (in time) vehicle located within a certain radius around the
        desired pickup point at the end of its plan is matched with the user. If no
        vehicle is or finishes its plan within the specified radius, returns an infinite
        waiting time.

        Args:
            -user: user requesting a ride
            -drop_node: node where user would like to be dropped off

        Returns:
            -service_dt: waiting time before pick-up
        """
        # Get all vehicles of the fleet
        vehs = np.array(list(self.fleet.vehicles.values()))
        if len(vehs) == 0:
            # There is no vehicle in the fleet, match is not possible
            return Dt(hours=24)

        # Search for the vehicles close to the user (within radius)
        vehs_pos = np.array([v.position for v in vehs])
        dist_vector = np.linalg.norm(vehs_pos - user.position, axis=1)
        nearest_vehs_indices = dist_vector <= self.radius # radius in meters
        nearest_vehs = vehs[nearest_vehs_indices]

        # If no vehicle surrounds the user, return inf service time
        if len(nearest_vehs) == 0:
            return Dt(hours=24)

        # Compute service time for these vehs
        candidates = []
        for veh in nearest_vehs:
            veh_last_node = veh.activity.node if not veh.activities else \
                    veh.activities[-1].node
            veh_path, tt = dijkstra(self.graph, veh_last_node, user.current_node, 'travel_time', {self.layer.id: self.id}, {self.layer.id})
            # If vehicle cannot reach user, skip and consider next vehicle
            if tt == float('inf'):
                continue

            # Compute the estimated pickup time including end of current vehicle's plan plus the pickup activity for user
            service_dt = Dt(seconds=tt)
            if veh.activity is not None and veh.activity.activity_type is not ActivityType.STOP:
                veh_curr_act_path_nodes = veh.path_to_nodes(veh.activity.path)
                veh_curr_node_ind_in_path = veh_curr_act_path_nodes.index(veh.current_node) # NB: works only when an acticity path does not contain several times the same node
                service_dt += Dt(seconds=compute_path_travel_time(veh.activity.path[veh_curr_node_ind_in_path+1:], self.graph, self.id))
                current_link = self.graph.nodes[veh.current_node].adj[veh_curr_act_path_nodes[veh_curr_node_ind_in_path+1]]
                service_dt += Dt(seconds=veh.remaining_link_length / current_link.costs[self.id]['speed'])
            for a in veh.activities:
                service_dt += Dt(seconds=compute_path_travel_time(a.path, self.graph, self.id))
            candidates.append((veh, service_dt, veh_path))

        # Select the veh with the smallest service time
        if candidates:
            candidates.sort(key=lambda x:x[1])
            self._cache_request_vehicles[user.id] = candidates[0][0], candidates[0][2]
        else:
            return Dt(hours=24)

        return candidates[0][1]

    # def request_nearest_idle_vehicle(self, user: User, drop_node: str) -> Dt:
    #     """Assigns the nearest idle vehicle to the requesting user.
    #
    #     Args:
    #         -user: User requesting a ride
    #         -drop_node: node where user would like to be dropped off
    #
    #     Returns:
    #         -service_dt: waiting time before pick-up
    #     """
    #
    #     upos = user.position
    #     uid = user.id
    #     vehs = list(self.fleet.vehicles.keys())
    #
    #     service_dt = Dt(hours=24)
    #
    #     while vehs:
    #
    #         # Search for the nearest vehicle to the user
    #         veh_pos = np.array([self.fleet.vehicles[v].position for v in vehs])
    #         dist_vector = np.linalg.norm(veh_pos - upos, axis=1)
    #         nearest_veh_index = np.argmin(dist_vector)
    #         nearest_veh = vehs[nearest_veh_index]
    #
    #         vehs.remove(nearest_veh)
    #
    #         choosen_veh = self.fleet.vehicles[nearest_veh]
    #         #if not choosen_veh.is_full:
    #         if choosen_veh.is_empty:
    #             # Vehicle available if either stopped or repositioning, and has no activity planned afterwards
    #             available = True if ((choosen_veh.activity_type in [ActivityType.STOP, ActivityType.REPOSITIONING]) and (not choosen_veh.activities)) else False
    #             if available:
    #                 # Compute pick-up path and cost from end of current activity
    #                 veh_last_node = choosen_veh.activity.node if not choosen_veh.activities else \
    #                 choosen_veh.activities[-1].node
    #                 veh_path, cost = dijkstra(self.graph, veh_last_node, user.current_node, 'travel_time', {self.layer.id: self.id}, {self.layer.id})
    #                 # If vehicle cannot reach user, skip and consider next vehicle
    #                 if cost == float('inf'):
    #                     continue
    #                     # raise PathNotFound(choosen_veh._current_node, user.current_node)
    #
    #                 service_dt = Dt(seconds=cost)
    #                 self._cache_request_vehicles[uid] = choosen_veh, veh_path
    #                 break
    #
    #     return service_dt

    def matching(self, user: User, drop_node: str):
        """Method that proceeds to the matching between a user and an already identified
        vehicle of this service.

        Args:
            -user: user to be matched
            -drop_node: node where user would like to be dropped off
        """
        veh, veh_path = self._cache_request_vehicles[user.id]
        log.info(f'User {user.id} matched with vehicle {veh.id} of mobility service {self._id}')
        upath = list(user.path.nodes)
        upath = upath[user.get_current_node_index():user.get_node_index_in_path(drop_node) + 1]
        user_path = self.construct_veh_path(upath)
        veh_path = self.construct_veh_path(veh_path)
        activities = [
            VehicleActivityPickup(node=user.current_node,
                                  path=veh_path,
                                  user=user),
            VehicleActivityServing(node=drop_node,
                                   path=user_path,
                                   user=user)
        ]

        veh.add_activities(activities)
        user.set_state_waiting_vehicle(veh)

        if veh.activity_type is ActivityType.STOP:
            veh.activity.is_done = True

    def replanning(self, veh: Vehicle, new_activities: List[VehicleActivity]) -> List[VehicleActivity]:
        pass

    def rebalancing(self, next_demand: List[User], horizon: List[Vehicle]):
        pass

    def service_level_costs(self, nodes: List[str]) -> dict:
        return create_service_costs()

    def __dump__(self):
        return {"TYPE": ".".join([OnDemandMobilityService.__module__, OnDemandMobilityService.__name__]),
                "DT_MATCHING": self._dt_matching,
                "VEH_CAPACITY": self._veh_capacity,
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data["DT_MATCHING"], data["VEH_CAPACITY"])
        return new_obj


class OnDemandDepotMobilityService(OnDemandMobilityService):
    def __init__(self,
                 id: str,
                 dt_matching: int,
                 dt_periodic_maintenance: int = 0,
                 matching_strategy: str = 'nearest_idle_vehicle_in_radius_fifo'):
        super(OnDemandDepotMobilityService, self).__init__(id, dt_matching, dt_periodic_maintenance,
            matching_strategy)
        self.gnodes = None
        self.depots = dict()

    def create_waiting_vehicle(self, node: str):
        """Method to create a vehicle at a certain node of the layer on which this
        mobility service runs.

        Args:
            -node: node at which the vehicle should be created

        Returns:
            -new_veh: the new vehicle
        """
        assert node in self.graph.nodes
        new_veh = self.fleet.create_vehicle(node,
                                            capacity=self._veh_capacity,
                                            activities=[VehicleActivityStop(node=node)])
        new_veh.set_position(self.graph.nodes[node].position)

        if self._observer is not None:
            new_veh.attach(self._observer)

        return new_veh

    def add_depot(self, node: str, capacity: int):
        """Method to create a depot full of vehicles.

        Args:
            -node: node where the depot should be created
            -capacity: maximum number of vehicles that can be parked in the depot
        """
        self.depots[node] = {"capacity": capacity,
                            "vehicles": set()}

        for _ in range(capacity):
            new_veh = self.create_waiting_vehicle(node)
            self.depots[node]["vehicles"].add(new_veh.id)

    def is_depot_full(self, node: str):
        """Method that checks if a depot has free parking spot or not.

        Args:
            -node: node where to check the depot state

        Returns:
            -full: boolean which is True if the depot is full, False otherwise
        """
        assert node in self.depots, f'Cannot find any depot located at {node} node'
        full = self.depots[node]["capacity"] <= len(self.depots[node]["vehicles"])
        return full

    def step_maintenance(self, dt: Dt):
        """Method that proceeds to the maintenance phase.
        It updates the dictionnary of nodes of the graph on which this mobility
        service runs.
        Moreover, it makes the stopped vehciles reposition themselves toward the nearest
        depot.

        Args:
            -dt: time elapsed since the previous maintenance phase
        """
        self.gnodes = self.graph.nodes

        depot = list(self.depots.keys())
        depot_pos = np.array([self.gnodes[d].position for d in depot])

        # For each stopped vehicle
        for veh in self.fleet.vehicles.values():
            if veh.activity_type is ActivityType.STOP:
                if veh._current_node not in self.depots:
                    # Find the nearest non full depot
                    veh_position = veh.position
                    dist_vector = np.linalg.norm(depot_pos - veh_position, axis=1)
                    sorted_ind = np.argsort(dist_vector)
                    nearest_depot = None
                    for nearest_depot_ind in sorted_ind:
                        current_depot = depot[nearest_depot_ind]
                        if not self.is_depot_full(current_depot):
                            nearest_depot = current_depot
                            break
                    # Get the shortest path till the nearest depot
                    veh_path, cost = dijkstra(self.graph,
                                              veh._current_node,
                                              nearest_depot,
                                              'travel_time',
                                              {self.layer.id: self.id,
                                               "TRANSIT": "WALK"},
                                              {self.layer.id})
                    if cost == float('inf'):
                        raise PathNotFound(veh._current_node, depot)
                    # Make the vehicle reposition till the nearest depot
                    veh_path = self.construct_veh_path(veh_path)
                    repositioning = VehicleActivityRepositioning(node=nearest_depot,
                                                                 path=veh_path)
                    veh.activity.is_done = True
                    veh.add_activities([repositioning])
                else:
                    # Vehicle is in the depot
                    self.depots[veh._current_node]["vehicles"].add(veh.id)

    def matching(self, user: User, drop_node: str):
        """Method that matches a user with an already identified vehicle of this
        service.

        Args:
            -user: user to be matched
            -drop_node: node where the user would like to be dropped off
        """
        veh, veh_path = self._cache_request_vehicles[user.id]
        log.info(f'User {user.id} matched with vehicle {veh.id} of mobility service {self._id}')
        upath = list(user.path.nodes)
        upath = upath[user.get_current_node_index():user.get_node_index_in_path(drop_node) + 1]

        user_path = self.construct_veh_path(upath)
        veh_path = self.construct_veh_path(veh_path)

        if veh_path:
            pickup = VehicleActivityPickup(node=user.current_node,
                                           path=veh_path,
                                           user=user)
        else:
            pickup = VehicleActivityPickup(node=user.current_node,
                                           path=veh_path,
                                           user=user,
                                           is_done=True)

        activities = [
            pickup,
            VehicleActivityServing(node=drop_node,
                                   path=user_path,
                                   user=user)
        ]

        veh.add_activities(activities)
        user.set_state_waiting_vehicle(veh)

        if veh.activity_type is ActivityType.STOP:
            veh.activity.is_done = True
            if veh._current_node in self.depots:
                # Remove the vehicle from the depot
                self.depots[veh._current_node]["vehicles"].remove(veh.id)

    def __dump__(self):
        return {"TYPE": ".".join([OnDemandMobilityService.__module__, OnDemandMobilityService.__name__]),
                "DT_MATCHING": self._dt_matching,
                "VEH_CAPACITY": self._veh_capacity,
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data["DT_MATCHING"], data["VEH_CAPACITY"])
        return new_obj
