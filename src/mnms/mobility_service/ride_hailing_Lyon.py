from typing import Tuple, Dict, List

import numpy as np
from scipy.optimize import linear_sum_assignment
import multiprocessing
import sys
import math

from hipop.shortest_path import dijkstra, parallel_dijkstra

from mnms import create_logger
from mnms.demand import User
from mnms.mobility_service.abstract import AbstractOnDemandMobilityService, AbstractOnDemandDepotMobilityService, \
    Request, compute_path_travel_time
from mnms.mobility_service.filters import PlanEndsInRadiusFilter, IsIdle, InRadiusFilter, DepotIsNotFull, \
    IsNearestDepotFilter
from mnms.time import Dt, Time
from mnms.tools.exceptions import PathNotFound
from mnms.vehicles.veh_type import ActivityType, VehicleActivityServing, VehicleActivityStop, \
    VehicleActivityPickup, VehicleActivityRepositioning, Vehicle, VehicleActivity
from mnms.tools.cost import create_service_costs
from mnms.tools.geometry import polygon_area, get_bounding_box

log = create_logger(__name__)


class RideHailingServiceLyon(AbstractOnDemandMobilityService):
    instances = []

    def __init__(self,
                 id: str,
                 dt_matching: int,
                 dt_periodic_maintenance: int = 0,
                 default_waiting_time: float = 0,
                 matching_strategy: str = 'nearest_idle_vehicle_in_radius_fifo',
                 radius: float = 2000,
                 detour_ratio: float = 1.343) -> object:
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
        super(RideHailingServiceLyon, self).__init__(id, veh_capacity=1, dt_matching=dt_matching,
                                                     dt_periodic_maintenance=dt_periodic_maintenance,
                                                     default_waiting_time=default_waiting_time)
        self.__class__.instances.append(self)
        self.gnodes = dict()
        self.detour_ratio = detour_ratio

        self._matching_strategy = matching_strategy
        self._radius = radius
        self._requests_history = []

        self.nb_of_users_counter = 0
        self.refused_users_counter = 0
        self.max_pickup_dist = 2000  # maximum tolerable pickup distance for a driver
        self.max_pickup_time = Time("00:10:00")  # max tolerable pickup time for a driver
        self.cancellation_mode = 0  #

        ####### Profits and costs ###########

        self.min_trip_price = 7
        self.service_km_profit = 1.7

        self.expenses_per_km = 0.3  # gaz + insurance + depreciation price
        self.idle_km_or_h_charge = 0 # per km

        self.driver_hour_min_payment = 18

        self.company_fee = 0.25  # percentage of profit that company takes from driver

    @property
    def matching_strategy(self):
        return self._matching_strategy

    @property
    def radius(self):
        return self._radius

    @property
    def requests_history(self):
        return self._requests_history

    def add_request(self, user: "User", drop_node: str, request_time: Time) -> None:
        """
        Add a new request to the mobility service defined by the user and her drop node.

        Args:
            -user: user object
            -drop_node: drop node id
            -request_time: time at which request is placed
        """
        super(RideHailingServiceLyon, self).add_request(user, drop_node, request_time)
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
            tau = (self.dt_matching + 1) * dt.to_seconds()

            # Oversupply mode
            if (len(idle_vehs_in_z) > len(open_reqs_in_z)) or (
                    len(idle_vehs_in_z) == len(open_reqs_in_z) and len(idle_vehs_in_z) > 0):
                idle_vehs_density_in_z = len(idle_vehs_in_z) / area
                w = tau / 2 + z.detour_ratio / (2 * mean_speed * math.sqrt(idle_vehs_density_in_z))
            # Undersupply mode
            elif (len(idle_vehs_in_z) < len(open_reqs_in_z)) or (
                    len(idle_vehs_in_z) == len(open_reqs_in_z) and len(open_reqs_in_z) > 0):
                open_reqs_density_in_z = len(open_reqs_in_z) / area
                # Compute mean requests arrival rate in this zone
                reqs_hist_pos = [self.gnodes[req.pickup_node].position for req in self.requests_history]
                mask = z.is_inside(reqs_hist_pos)
                reqs_hist_in_z = np.array(self.requests_history)[mask]
                if len(reqs_hist_in_z) == 0:
                    log.warning(
                        f'There is no request history in zone {zid}, impossible to estimate pickup time there...')
                    continue
                delta_t = (max(reqs_hist_in_z).request_time - min(reqs_hist_in_z).request_time).to_seconds()
                if delta_t == 0:
                    delta_t = dt.to_seconds()  # dt is the smallest time step
                reqs_arrival_rate_in_z = len(reqs_hist_in_z) / delta_t
                # Deduce estimates waiting time
                w = len(open_reqs_in_z) / reqs_arrival_rate_in_z - tau / 2 + z.detour_ratio / (
                        mean_speed * math.sqrt(math.pi * open_reqs_density_in_z))
            # No idle vehicle nor open request : apply default waiting time
            else:
                w = self.default_waiting_time
            self._estimated_pickup_times[zid] = w
        # Check that all links of this service's layer have been treated
        if len(self.zones) > 0 and count_links_treated < len(glinks):
            log.warning(f'Incomplete zoning defined for {self.id} service, we compute ' \
                        'the estimated waiting time on remaining links considering the whole network...')

        # Treat links all together when no zone is defined
        if len(self.zones) == 0 or (len(self.zones) > 0 and count_links_treated < len(glinks)):
            # Count the nb of idle vehicles on the whole network
            idle_vehs = self.get_idle_vehicles()

            # Count the nb of open requests on the whole network
            open_reqs = list(self.user_buffer.values())

            tau = (self.dt_matching + 1) * dt.to_seconds()
            bbox = get_bounding_box(None, graph=self.graph)
            area = max(1, (bbox.xmax - bbox.xmin)) * max(1, (bbox.ymax - bbox.ymin))  # max(1,-) for flat networks
            mean_speed = np.mean([glinks[lid].costs[self.id]['speed'] for lid in glinks])
            delta_t = (max(open_reqs).request_time - min(open_reqs).request_time).to_seconds() if open_reqs else np.nan
            if delta_t == 0:
                delta_t = dt.to_seconds()  # dt is the smallest time step

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
                    delta_t = dt.to_seconds()  # dt is the smallest time step
                reqs_arrival_rate = len(reqs_hist) / delta_t
                w = len(open_reqs) / reqs_arrival_rate - tau / 2 + self.detour_ratio / (
                        mean_speed * math.sqrt(math.pi * open_reqs_density))
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
            elif self.matching_strategy in ['nearest_idle_vehicle_in_radius_batched',
                                            'nearest_vehicle_in_radius_batched']:
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
                tup = self.request_nearest_idle_vehicle_in_radius_fifo(user, drop_node)
                if type(tup) is Dt:
                    service_dt = self.request_nearest_idle_vehicle_in_radius_fifo(user, drop_node)
                else:
                    service_dt = tup[0]
                    idle_service_dt = tup[1]
                    driver_profit_per_trip = tup[2]
            elif self.matching_strategy == 'nearest_vehicle_in_radius_fifo':
                service_dt = self.request_nearest_vehicle_in_radius_fifo(user, drop_node)
            else:
                log.error(f'Matching strategy {self.matching_strategy} unknown for {self.id} mobility service')
                sys.exit(-1)
            # Check pick-up time proposition compared with user waiting tolerance
            if user.pickup_dt[self.id] > service_dt:
                # Match user with vehicle
                self.matching(req, dt)

                self.profit_update(user, driver_profit_per_trip)
                # Remove user from list of users waiting to be matched
                self.cancel_request(user.id)
            else:
                log.info(
                    f"{user.id} refused {self.id} offer (predicted pickup time ({service_dt}) is too long, wait for better proposition...")
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
        inf = 10e8  # will be applied when veh is out of request's radius or service time out of user's tolerance
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
            if len(vehs)>0:
                mask = filter.get_mask(self.layer, vehs, position=req.user.position)
            else:
                mask = False
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
                                      [{self.layer.id: self.id}] * len(origins),
                                      'travel_time',
                                      multiprocessing.cpu_count(),
                                      [{self.layer.id}] * len(origins))
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
                veh_curr_node_ind_in_path = veh_curr_act_path_nodes.index(
                    veh.current_node)  # NB: works only when an acticity path does not contain several times the same node
                service_dt += Dt(
                    seconds=compute_path_travel_time(veh.activity.path[veh_curr_node_ind_in_path + 1:], self.graph,
                                                     self.id))
                current_link = self.gnodes[veh.current_node].adj[veh_curr_act_path_nodes[veh_curr_node_ind_in_path+1]]
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

                # LB add driver profit for batch matching
                veh_path_idle = veh_path
                cost_idle = pickup_times_matrix[req_ind][veh_ind]
                len_path_idle = 0  # idle distance in meters
                for i in range(len(veh_path_idle) - 1):
                    j = i + 1
                    len_path_idle += self.gnodes[veh_path_idle[i]].adj[veh_path_idle[j]].length

                user = req.user
                upath = list(user.path.nodes)
                len_path_service = 0  # service distance in meters
                cost_service = 0
                for i in range(1, len(upath) - 2):
                    j = i + 1
                    len_path_service += self.gnodes[upath[i]].adj[upath[j]].length
                    link = self.gnodes[upath[i]].adj[upath[j]]
                    cost_service += link.costs[self.id]["travel_time"]

                driver_profit = (len_path_service * self.service_km_profit) / 1000
                expenses_per_km = ((len_path_idle + len_path_service) * self.expenses_per_km) / 1000
                idle_charge = (len_path_idle * self.idle_km_or_h_charge) / 1000
                total_profit = max(driver_profit, self.min_trip_price) - expenses_per_km - idle_charge
                threshold = ((cost_idle + cost_service) * self.driver_hour_min_payment) / 3600

                driver_profit_per_trip = total_profit
                if total_profit >= threshold:
                    self._cache_request_vehicles[req.user.id] = veh, veh_path
                    self.matching(req, dt)
                    self.cancel_request(req.user.id)
                    self.profit_update(user, driver_profit_per_trip)
            self._cache_request_vehicles = dict()

    def request_nearest_idle_vehicle_in_radius_fifo(self, user: User, drop_node: str) -> Dt | tuple[
        Dt, Dt, float | int]:
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

        origins = [veh.current_node for veh in idle_vehs_in_radius]
        destinations = [user.current_node] * len(idle_vehs_in_radius)
        try:
            paths = parallel_dijkstra(self.graph,
                                      origins,
                                      destinations,
                                      [{self.layer.id: self.id}] * len(origins),
                                      'travel_time',
                                      multiprocessing.cpu_count(),
                                      [{self.layer.id}] * len(origins))
        except ValueError as ex:
            log.error(f'HiPOP.Error: {ex}')
            sys.exit(-1)

        # Compute pickup time to reach the user for the idle vehs in radius
        candidates = []

        idle_service_dt = Dt(hours=24)
        occupied_service_dt = Dt(hours=24)

        for i, (veh_path_idle, cost_idle) in enumerate(paths):
            if cost_idle == float('inf'):
                # This vehicle cannot reach user, skip and consider next vehicle
                continue
            veh = idle_vehs_in_radius[i]
            len_path_idle = 0  # idle distance in meters
            for i in range(len(veh_path_idle) - 1):
                j = i + 1
                len_path_idle += self.gnodes[veh_path_idle[i]].adj[veh_path_idle[j]].length
            # veh_path_service, cost_service = dijkstra(self.graph, user.current_node, user.path.nodes[-2], 'travel_time',
            #                                          {self.layer.id: self.id}, {self.layer.id})
            upath = list(user.path.nodes)
            len_path_service = 0  # service distance in meters
            cost_service = 0
            for i in range(1, len(upath) - 2):
                j = i + 1
                len_path_service += self.gnodes[upath[i]].adj[upath[j]].length
                link = self.gnodes[upath[i]].adj[upath[j]]
                cost_service += link.costs[self.id]["travel_time"]

            driver_profit = (len_path_service * self.service_km_profit) / 1000
            expenses_per_km = ((len_path_idle + len_path_service) * self.expenses_per_km) / 1000
            idle_charge = (len_path_idle * self.idle_km_or_h_charge) / 1000
            total_profit = max(driver_profit, self.min_trip_price) - expenses_per_km - idle_charge
            threshold = ((cost_idle + cost_service) * self.driver_hour_min_payment) / 3600
            if total_profit >= threshold:
                idle_service_dt = Dt(seconds=cost_idle)  # idle time (time needed to pickup a user)
                candidates.append((veh, idle_service_dt, veh_path_idle))
                break
            else:
                continue

        # Select the veh with the smallest pickup time, and not the highest profit as vehs don't know the profit of each other, it's the nearest veh that takes the request
        if candidates:
            candidates.sort(key=lambda x: x[1])
            self._cache_request_vehicles[user.id] = candidates[0][0], candidates[0][2]
        else:
            return Dt(hours=24)
        tup = (candidates[0][1], idle_service_dt, total_profit)
        return tup

    def profit_update(self, user: User, driver_profit_per_trip: float):
        veh, veh_path = self._cache_request_vehicles[user.id]
        veh.trip_counter_update()
        veh.driver_profit_update(driver_profit_per_trip)

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
                veh_path, tt = dijkstra(self.graph, veh_last_node, user.current_node, 'travel_time',
                                        {self.layer.id: self.id}, {self.layer.id})
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
                veh_curr_node_ind_in_path = veh_curr_act_path_nodes.index(
                    veh.current_node)  # NB: works only when an acticity path does not contain several times the same node
                service_dt += Dt(
                    seconds=compute_path_travel_time(veh.activity.path[veh_curr_node_ind_in_path + 1:], self.graph,
                                                     self.id))
                current_link = self.gnodes[veh.current_node].adj[veh_curr_act_path_nodes[veh_curr_node_ind_in_path+1]]
                service_dt += Dt(seconds=veh.remaining_link_length / current_link.costs[self.id]['speed'])
            for a in veh.activities:
                service_dt += Dt(seconds=compute_path_travel_time(a.path, self.graph, self.id))
            candidates.append((veh, service_dt, veh_path))

        # Select the veh with the smallest service time
        if candidates:
            candidates.sort(key=lambda x: x[1])
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
        upath = upath[user.get_current_node_index():user.get_node_index_in_path(
            drop_node) + 1]  # service path, I can loop through the list of nodes which will give me each link, and on each link there is an attribute called smth like 'cost'
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
        return {"TYPE": ".".join([RideHailingServiceLyon.__module__, RideHailingServiceLyon.__name__]),
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
