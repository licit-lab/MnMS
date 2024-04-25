from typing import Tuple, Dict, List

import numpy as np
from scipy.optimize import linear_sum_assignment
import multiprocessing
import sys
import math

from hipop.shortest_path import dijkstra, parallel_dijkstra

from mnms import create_logger
from mnms.demand import User
from mnms.mobility_service.abstract import AbstractOnDemandMobilityService, AbstractOnDemandDepotMobilityService, Request, compute_path_travel_time, compute_path_nodes_travel_time
from mnms.mobility_service.filters import PlanEndsInRadiusFilter, IsIdle, InRadiusFilter, DepotIsNotFull, IsNearestDepotFilter
from mnms.time import Dt, Time
from mnms.tools.exceptions import PathNotFound
from mnms.vehicles.veh_type import ActivityType, VehicleActivityServing, VehicleActivityStop, \
    VehicleActivityPickup, VehicleActivityRepositioning, Vehicle, VehicleActivity
from mnms.tools.cost import create_service_costs
from mnms.tools.geometry import polygon_area, get_bounding_box
from mnms.tools.preprocessing import decode_shortest_path_tree

log = create_logger(__name__)


class OnDemandMobilityService(AbstractOnDemandMobilityService):

    def __init__(self,
                 id: str,
                 dt_matching: int,
                 dt_periodic_maintenance: int = 0,
                 default_waiting_time: float = 0,
                 matching_strategy: str='nearest_idle_vehicle_in_radius_fifo',
                 radius: float = 10000,
                 detour_ratio: float = 1.343):
        """Constructor of an OnDemandMobilityService object.

        Args:
            -id: id of the service
            -dt_matching: the number of flow time steps elapsed between two calls
             of the matching
            -dt_periodic_maintenance: the number of flow steps elapsed between two
             call of the periodic maintenance
            -default_waiting_time: default estimated waiting time broadcasted to users at
             the moment of their planning, it is applied initially and when there is no
             idle vehicle nor open request
            -matching_strategy: strategy to apply for the matching
            -radius: radius in meters used by matching strategies
            -detour_ratio: distance on the actual road network to straight line distance
        """
        super(OnDemandMobilityService, self).__init__(id, veh_capacity=1, dt_matching=dt_matching,
            dt_periodic_maintenance=dt_periodic_maintenance, default_waiting_time=default_waiting_time)
        self.gnodes = dict()
        self.detour_ratio = detour_ratio

        self._matching_strategy = matching_strategy
        self._radius = radius
        self._requests_history = []

    @property
    def matching_strategy(self):
        return self._matching_strategy

    @property
    def radius(self):
        return self._radius

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
        super(OnDemandMobilityService, self).add_request(user, drop_node, request_time)
        # Save the request in the proper zone to be able to compute request arrival rate
        self._requests_history.append(Request(user, drop_node, request_time))

    def step_maintenance(self, dt: Dt):
        """Method that proceeds to the maintenance phase. It updates the dictionnary
        of nodes of the graph on which this mobility service runs (TODO: check if this
        is really needed). Also, it computes the estimated waiting time(s) for a request
        in each zone of this service.

        Args:
            -dt: time elapsed since the previous maintenance phase
        """
        # Update dict of graph nodes
        self.gnodes = self.graph.nodes

        # (Re)compute estimated pickup times
        self.update_estimated_pickup_times(dt)

    def update_estimated_pickup_times(self, dt: Dt):
        """Method that computes the estimated waiting time(s) for a request
        in each zone of this service.

        Args:
            -dt: time elapsed since the previous maintenance phase
        """
        # Treat zone per zone when they are defined
        glinks = self.graph.links
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
                reqs_hist_pos = [self.gnodes[req.pickup_node].position for req in self.requests_history]
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

    def launch_matching(self, new_users, user_flow, decision_model, dt):
        """
        Method that launches the matching phase.

        Args:
            -new_users: users who have chosen a path but not yet departed
            -user_flow: the UserFlow object of the simulation
            -decision_model: the AbstractDecisionModel object of the simulation
            -dt: time since last call of this method (flow time step)
        """
        if self._counter_matching == self.dt_matching:
            # Trigger a matching phase
            self._counter_matching = 0
            if self.matching_strategy in ['nearest_idle_vehicle_in_radius_fifo', 'nearest_vehicle_in_radius_fifo']:
                self.launch_matching_fifo(dt)
            elif self.matching_strategy in ['nearest_idle_vehicle_in_radius_batched', 'nearest_vehicle_in_radius_batched']:
                self.launch_matching_batch(dt)
            else:
                log.error(f'Matching strategy {self.matching_strategy} unknown for {self.id} mobility service')
                sys.exit(-1)
            # (Re)compute estimated pickup times after this matching phase
            self.update_estimated_pickup_times(dt)
        else:
            # Do not trigger a matching phase
            self._counter_matching += 1

    def launch_matching_fifo(self, dt):
        """Method that launches the matching phase by treating the requests one by
        one in  order of arrival.

        Args:
            -dt: the flow time step
        """
        reqs = list(self.user_buffer.values())
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
                self.matching(req, dt)
                # Remove user from list of users waiting to be matched
                self.cancel_request(user.id)
            else:
                log.info(f"{user.id} refused {self.id} offer (predicted pickup time ({service_dt}) is too long, wait for better proposition...")
            self._cache_request_vehicles = dict()

    def launch_matching_batch(self, dt):
        """Method that launches the matching phase by treating the requests jointly.

        Args:
            -dt: the flow time step
        """
        ### Get the batches of requests and considered vehicles
        reqs = list(self.user_buffer.values())
        if self.matching_strategy == 'nearest_idle_vehicle_in_radius_batched':
            vehs = self.get_idle_vehicles()
        elif self.matching_strategy == 'nearest_vehicle_in_radius_batched':
            vehs = self.get_all_vehicles()
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
            # Search for the vehicles close to the user at the end of their plan (within radius)
            filter = PlanEndsInRadiusFilter(self.radius)
            mask = filter.get_mask(self.layer, vehs, position=req.user.position)
            nearest_vehs = vehs[mask]
            nearest_vehs_indices = list(np.where(mask)[0])

            # Compute estimated pickup time for the vehicles nearby
            for vidx, veh in zip(nearest_vehs_indices, nearest_vehs):
                veh_last_node = veh.activity.node if not veh.activities else \
                        veh.activities[-1].node
                ridxs.append(ridx)
                vidxs.append(vidx)
                origins.append(veh_last_node)
                destinations.append(req.user.current_node)

        ## Call Dijkstra once
        try:
            paths = parallel_dijkstra(self.graph,
                                    origins,
                                    destinations,
                                    [{self.layer.id: self.id}]*len(origins),
                                    'travel_time',
                                    multiprocessing.cpu_count(),
                                    [{self.layer.id}]*len(origins))
        except ValueError as ex:
            log.error(f'HiPOP.Error: {ex}')
            sys.exit(-1)

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
                service_dt += Dt(seconds=compute_path_travel_time(veh.activity.path[veh_curr_node_ind_in_path+1:], self.gnodes, self.id))
                current_link = self.gnodes[veh.current_node].adj[veh_curr_act_path_nodes[veh_curr_node_ind_in_path+1]]
                service_dt += Dt(seconds=veh.remaining_link_length / current_link.costs[self.id]['speed'])
            for a in veh.activities:
                service_dt += Dt(seconds=compute_path_travel_time(a.path, self.gnodes, self.id))
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
                self.matching(req, dt)
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
        # Get all idle vehicles of the fleet within radius around user
        filter = IsIdle() & InRadiusFilter(self.radius)
        all_vehs = self.get_all_vehicles()
        mask = filter.get_mask(self.layer, all_vehs, position=user.position)
        idle_vehs_in_radius = all_vehs[mask]
        if len(idle_vehs_in_radius) == 0:
            # There is no idle vehicle in radius, match is not possible
            return Dt(hours=24)

        # Compute service time for the idle vehs in radius
        origins = [veh.current_node for veh in idle_vehs_in_radius]
        destinations = [user.current_node] * len(idle_vehs_in_radius)
        if self.layer.shortest_paths is not None:
            # Let's read the shortest paths
            paths = []
            for o,d in zip(origins, destinations):
                veh_path = decode_shortest_path_tree(self.layer.shortest_paths, o, d)
                if o != d and len(veh_path) > 1:
                    # Compute the travel time
                    tt = compute_path_nodes_travel_time(veh_path, self.gnodes, self.id)
                elif o == d:
                    veh_path = []
                    tt = 0
                else:
                    tt = float('inf')
                paths.append((veh_path, tt))
        else:
            # Let's compute the shortest paths
            try:
                paths = parallel_dijkstra(self.graph,
                                        origins,
                                        destinations,
                                        [{self.layer.id: self.id}]*len(origins),
                                        'travel_time',
                                        multiprocessing.cpu_count(),
                                        [{self.layer.id}]*len(origins))
            except ValueError as ex:
                log.error(f'HiPOP.Error: {ex}')
                sys.exit(-1)

        # Gather valid candidates
        candidates = []
        for i, (veh_path, tt) in enumerate(paths):
            if tt == float('inf'):
                # This vehicle cannot reach user, skip and consider next vehicle
                continue
            veh = idle_vehs_in_radius[i]
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
        # Get all vehicles of the fleet within radius around user at the end of their plan
        filter = PlanEndsInRadiusFilter(self.radius)
        all_vehs = self.get_all_vehicles()
        mask = filter.get_mask(self.layer, all_vehs, position=user.position)
        vehs_in_radius = all_vehs[mask]
        if len(vehs_in_radius) == 0:
            # There is no vehicle in radius at the end of their plan
            return Dt(hours=24)

        # Compute service time for these vehs
        candidates = []
        for veh in vehs_in_radius:
            veh_last_node = veh.activity.node if not veh.activities else \
                    veh.activities[-1].node
            try:
                veh_path, tt = dijkstra(self.graph, veh_last_node, user.current_node, 'travel_time', {self.layer.id: self.id}, {self.layer.id})
            except ValueError as ex:
                log.error(f'HiPOP.Error: {ex}')
                sys.exit(-1)
            # If vehicle cannot reach user, skip and consider next vehicle
            if tt == float('inf'):
                continue

            # Compute the estimated pickup time including end of current vehicle's plan plus the pickup activity for user
            service_dt = Dt(seconds=tt)
            if veh.activity is not None and veh.activity.activity_type is not ActivityType.STOP:
                veh_curr_act_path_nodes = veh.path_to_nodes(veh.activity.path)
                veh_curr_node_ind_in_path = veh_curr_act_path_nodes.index(veh.current_node) # NB: works only when an acticity path does not contain several times the same node
                service_dt += Dt(seconds=compute_path_travel_time(veh.activity.path[veh_curr_node_ind_in_path+1:], self.gnodes, self.id))
                current_link = self.gnodes[veh.current_node].adj[veh_curr_act_path_nodes[veh_curr_node_ind_in_path+1]]
                service_dt += Dt(seconds=veh.remaining_link_length / current_link.costs[self.id]['speed'])
            for a in veh.activities:
                service_dt += Dt(seconds=compute_path_travel_time(a.path, self.gnodes, self.id))
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
    #                 try:
    #                     veh_path, cost = dijkstra(self.graph, veh_last_node, user.current_node, 'travel_time', {self.layer.id: self.id}, {self.layer.id})
    #                 except ValueError as ex:
    #                     log.error(f'HiPOP.Error: {ex}')
    #                     sys.exit(-1)
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

    def matching(self, request: Request, dt: Dt):
        """Method that proceeds to the matching between a user and an already identified
        vehicle of this service.

        Args:
            -request: the request to match
            -dt: the flow time step
        """
        user = request.user
        drop_node = request.drop_node
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
            immediate_match = len(veh.activities) == 2 and len(veh_path) == 0 \
                and self._tcurrent - request.request_time <= dt
            if immediate_match:
                # This is an immediate match, take into account effective remaining
                # duration to move during the current flow step
                veh.dt_move = self._tcurrent - request.request_time

    def __dump__(self):
        return {"TYPE": ".".join([OnDemandMobilityService.__module__, OnDemandMobilityService.__name__]),
                "DT_MATCHING": self.dt_matching,
                "DT_PERIODIC_MAINTENANCE": self._dt_periodic_maintenance,
                "ID": self.id,
                "DEFAULT_WAITING_TIME": self.default_waiting_time,
                "MATCHING_STRATEGY": self.matching_strategy,
                "RADIUS": self.radius,
                "DETOUR_RATIO": self.detour_ratio}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data['DT_MATCHING'], data['DT_PERIODIC_MAINTENANCE'],
            data['DEFAULT_WAITING_TIME'], data['MATCHING_STRATEGY'], data['RADIUS'],
            data['DETOUR_RATIO'])
        return new_obj


class OnDemandDepotMobilityService(OnDemandMobilityService, AbstractOnDemandDepotMobilityService):
    def __init__(self,
                 id: str,
                 dt_matching: int,
                 dt_periodic_maintenance: int = 0,
                 default_waiting_time: float = 0,
                 matching_strategy: str = 'nearest_idle_vehicle_in_radius_fifo',
                 radius: float = 10000,
                 detour_ratio: float = 1.343):
        super(OnDemandDepotMobilityService, self).__init__(id, dt_matching, dt_periodic_maintenance=dt_periodic_maintenance,
            matching_strategy=matching_strategy, radius=radius, detour_ratio=detour_ratio, default_waiting_time=default_waiting_time)
        #NB: super is the first mother class, do not init the second mother class because
        #    it contains the same attributes except depots
        self.gnodes = None
        self.depots = dict()

    def step_maintenance(self, dt: Dt):
        """Method that proceeds to the maintenance phase.
        It updates the dictionnary of nodes of the graph on which this mobility
        service runs.
        Moreover, it makes the stopped vehciles reposition themselves toward the nearest
        depot.

        Args:
            -dt: time elapsed since the previous maintenance phase
        """
        ## Update graph nodes
        self.gnodes = self.graph.nodes

        # (Re)compute estimated pickup times
        self.update_estimated_pickup_times(dt)

        ## Make stopped vehicles reposition toward the closest non full depot
        depots = self.get_all_depots()
        # For each stopped vehicle
        for veh in self.fleet.vehicles.values():
            if veh.activity_type is ActivityType.STOP:
                if veh._current_node not in self.depots:
                    # Find the nearest non full depot
                    filter = DepotIsNotFull() & IsNearestDepotFilter()
                    mask = filter.get_mask(self.layer, depots, position=veh.position)
                    nearest_depot = depots[mask]
                    if len(nearest_depot) > 0:
                        # Get the shortest path till the nearest depot
                        nearest_depot = nearest_depot[0]
                        try:
                            veh_path, cost = dijkstra(self.graph,
                                                    veh._current_node,
                                                    nearest_depot.node,
                                                    'travel_time',
                                                    {self.layer.id: self.id,
                                                    "TRANSIT": "WALK"},
                                                    {self.layer.id})
                        except ValueError as ex:
                            log.error(f'HiPOP.Error: {ex}')
                            sys.exit(-1)
                        if cost == float('inf'):
                            raise PathNotFound(veh._current_node, depots)
                        # Make the vehicle reposition till the nearest depot
                        veh_path = self.construct_veh_path(veh_path)
                        repositioning = VehicleActivityRepositioning(node=nearest_depot.node,
                                                                 path=veh_path)
                        veh.activity.is_done = True
                        veh.add_activities([repositioning])
                else:
                    # Add the vehicle in the depot if it is not yet inside
                    if not self.depots[veh._current_node].contains(veh):
                        self.depots[veh._current_node].add_vehicle(veh, None)

    def matching(self, request: Request, dt: Dt):
        """Method that matches a user with an already identified vehicle of this
        service.

        Args:
            -request: the request to match
            -dt: flow time step
        """
        user = request.user
        drop_node = request.drop_node
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
            immediate_match = len(veh.activities) == 2 and len(veh_path) == 0 \
                and self._tcurrent - request.request_time <= dt
            if immediate_match:
                # This is an immediate match , take into account effective remaining
                # duration to move during the current flow step
                veh.dt_move = self._tcurrent - request.request_time

            if veh._current_node in self.depots:
                # Remove the vehicle from the depot
                self.depots[veh._current_node].remove_vehicle(veh)

    def __dump__(self):
        return {"TYPE": ".".join([OnDemandMobilityService.__module__, OnDemandMobilityService.__name__]),
                "DT_MATCHING": self.dt_matching,
                "DT_PERIODIC_MAINTENANCE": self._dt_periodic_maintenance,
                "ID": self.id,
                "DEFAULT_WAITING_TIME": self.default_waiting_time,
                "MATCHING_STRATEGY": self.matching_strategy,
                "RADIUS": self.radius,
                "DETOUR_RATIO": self.detour_ratio}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data["DT_MATCHING"], data["DT_PERIODIC_MAINTENANCE"],
            data['DEFAULT_WAITING_TIME'], data['MATCHING_STRATEGY'], data['RADIUS'],
            data['DETOUR_RATIO'])
        return new_obj
