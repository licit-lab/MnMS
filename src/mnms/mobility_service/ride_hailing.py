from typing import Tuple, Dict

import numpy as np

from hipop.shortest_path import dijkstra

from mnms import create_logger
from mnms.demand import User
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.time import Dt
from mnms.tools.exceptions import PathNotFound
from mnms.vehicles.veh_type import ActivityType, VehicleActivityServing, VehicleActivityStop, \
    VehicleActivityPickup, VehicleActivityRepositioning, Vehicle
from mnms.time import Time

log = create_logger(__name__)

class RideHailingService(AbstractMobilityService):

    instances = []

    def __init__(self,
                 _id: str,
                 dt_matching: int,  # indicates how often we perform matching (eg, to indicate that we match users&vehicles every 2 min)
                 dt_step_maintenance: int = 0):
        super(RideHailingService, self).__init__(_id, 1, dt_matching, dt_step_maintenance)

        self.__class__.instances.append(self)
        self.gnodes = dict()
        self.nb_of_users_counter = 0
        self.refused_users_counter = 0
        #self.max_pickup_dist = 2000                # maximum tolerable pickup distance for a driver
        #self.max_pickup_time = Time("00:10:00")    # max tolerable pickup time for a driver
        self.cancellation_mode = 0                 #

    def create_waiting_vehicle(self, node: str):
        assert node in self.graph.nodes
        new_veh = self.fleet.create_vehicle(node,
                                            capacity=self._veh_capacity,
                                            activities=[VehicleActivityStop(node=node)])
        new_veh.set_position(self.graph.nodes[node].position)

        if self._observer is not None:
            new_veh.attach(self._observer)

    def step_maintenance(self, dt: Dt):
        self.gnodes = self.graph.nodes

    def request(self, user: User, drop_node: str) -> tuple[Dt, int]:
        """
                Args:
                    user: User requesting a ride
                    drop_node:
                Returns: waiting time before pick-up
                """

        upos = user.position
        uid = user.id
        vehs = list(self.fleet.vehicles.keys())
        idle_service_dt = Dt(hours=24)
        occupied_service_dt = Dt(hours=24)
        total_profit = 0
        while vehs:
            # Search for the nearest vehicle to the user
            veh_pos = np.array([self.fleet.vehicles[v].position for v in vehs])
            dist_vector = np.linalg.norm(veh_pos - upos, axis=1)
            nearest_veh_index = np.argmin(dist_vector)
            nearest_veh = vehs[nearest_veh_index]
            vehs.remove(nearest_veh)

            choosen_veh = self.fleet.vehicles[nearest_veh]
            #            if not choosen_veh.is_full:
            if choosen_veh.is_empty:
                # Vehicle available if either stopped or repositioning, and has no activity planned afterwards
                available = True if ((choosen_veh.activity_type in [ActivityType.STOP, ActivityType.REPOSITIONING]) and (
                    not choosen_veh.activities)) else False
                if available:
                    # Compute pick-up path and cost from end of current activity
                    veh_last_node = choosen_veh.activity.node if not choosen_veh.activities else \
                        choosen_veh.activities[-1].node
                    veh_path_idle, cost_idle = dijkstra(self.graph, veh_last_node, user.current_node, 'travel_time',
                                              {self.layer.id: self.id}, {self.layer.id})    # veh_path_idle - path as sequence of nodes, cost - time cost_idle
                    # If vehicle cannot reach user, skip and consider next vehicle
                    if cost_idle == float('inf'):
                        continue
                    len_path_idle = 0           # idle distance in meters
                    for i in range(len(veh_path_idle) - 1):
                        j = i + 1
                        len_path_idle += self.gnodes[veh_path_idle[i]].adj[veh_path_idle[j]].length
                    #idle_service_dt = Dt(seconds=len_path / choosen_veh.speed)
                    idle_service_dt = Dt(seconds=cost_idle)     # idle time (time needed to pickup a user)

                    ##############################
                    veh_path_service, cost_service = dijkstra(self.graph, user.current_node, user.path.nodes[-2], 'travel_time',
                                                        {self.layer.id: self.id}, {self.layer.id})
                    if cost_idle == float('inf'):
                        continue
                    len_path_service = 0                # service distance in meters
                    for i in range(len(veh_path_service) - 1):
                        j = i + 1
                        len_path_service += self.gnodes[veh_path_service[i]].adj[veh_path_service[j]].length
                    occupied_service_dt = Dt(seconds=cost_service)          # service time (from pickup to dropoff)

                    total_profit = 0

                    ###############################
                    self._cache_request_vehicles[uid] = choosen_veh, veh_path_idle
                    break
        return idle_service_dt, total_profit

    def profit_update(self, user: User, driver_profit_per_trip: float):
        veh, veh_path = self._cache_request_vehicles[user.id]
        veh.trip_counter_update()
        veh.driver_profit_update(driver_profit_per_trip)

    def matching(self, user: User, drop_node: str):
        veh, veh_path = self._cache_request_vehicles[user.id]
        upath = list(user.path.nodes)
        upath = upath[upath.index(user._current_node):upath.index(drop_node) + 1]
        user_path = self.construct_veh_path(upath)
        veh_path = self.construct_veh_path(veh_path)
        activities = [
            VehicleActivityPickup(node=user._current_node,
                                  path=veh_path,
                                  user=user),
            VehicleActivityServing(node=drop_node,
                                   path=user_path,
                                   user=user)
        ]

        veh.add_activities(activities)
        user.set_state_waiting_vehicle()

        if veh.activity_type is ActivityType.STOP:
            veh.activity.is_done = True

    def launch_matching(self):
        """
                Method that launch passenger-vehicles matching, through 1. requesting and 2. matching.
                Returns: empty list # TODO - should be cleaned

                """
        # refuse_user = list()

        if self._counter_matching == self._dt_matching:
            self._counter_matching = 0

            for uid, (user, drop_node) in list(self._user_buffer.items()):
                # User makes service request
                service_dt, driver_profit_per_trip = self.request(user, drop_node)

                if user.pickup_dt[self.id] > service_dt:
                    # If pick-up time is below passengers' waiting tolerance
                    # Match user with vehicle
                    self.matching(user, drop_node)

                    self.profit_update(user, driver_profit_per_trip)
                    # Remove user from list of users waiting to be matched
                    self._user_buffer.pop(uid)
                else:
                    # If pick-up time exceeds passengers' waiting tolerance
                    log.info(f"{uid} refused {self.id} offer (predicted pickup time too long)")
                    #user.set_state_stop()
                    #user.notify(self._tcurrent)
                    #refuse_user.append(user)
                self._cache_request_vehicles = dict()

            #self._user_buffer = dict()
            # NB: we clean _user_buffer here because answer provided by the mobility
            #     service should be YES I match with you or No I refuse you, but not
            #     let's wait the next timestep to see if I can find a vehicle for you
            #     Mob service has only one chance to propose a match to the user,
            #     except if user request the service again
        else:
            self._counter_matching += 1

        return list()  # refuse_user        # list of refused users?

    def __dump__(self):
        return {"TYPE": ".".join([RideHailingService.__module__, RideHailingService.__name__]),
                "DT_MATCHING": self._dt_matching,
                "VEH_CAPACITY": self._veh_capacity,
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data["DT_MATCHING"], data["VEH_CAPACITY"])
        return new_obj


class RideHailingServiceIdleCharge(AbstractMobilityService):        # charge per idle km

    instances = []

    def __init__(self,
                 _id: str,
                 dt_matching: int,      ## indicates how often we perform matching (eg, to indicate that we match users&vehicles every 2 min)
                 dt_step_maintenance: int = 0):
        super(RideHailingServiceIdleCharge, self).__init__(_id, 1, dt_matching, dt_step_maintenance)

        self.__class__.instances.append(self)
        self.gnodes = dict()
        self.nb_of_users_counter = 0
        self.refused_users_counter = 0
        #self.max_pickup_dist = 2000                # maximum tolerable pickup distance for a driver
        #self.max_pickup_time = Time("00:10:00")    # max tolerable pickup time for a driver
        self.cancellation_mode = 0                 #

        ####### Profits and costs ###########

        self.min_trip_price = 7
        self.service_km_profit = 1.7

        self.expenses_per_km = 0.3     # gaz + insurance + depreciation price
        self.idle_km_or_h_charge = 0

        self.driver_hour_min_payment = 18

        self.company_fee = 0.25          # percentage of profit that company takes from driver

    def create_waiting_vehicle(self, node: str):
        assert node in self.graph.nodes
        new_veh = self.fleet.create_vehicle(node,
                                            capacity=self._veh_capacity,
                                            activities=[VehicleActivityStop(node=node)])
        new_veh.set_position(self.graph.nodes[node].position)

        if self._observer is not None:
            new_veh.attach(self._observer)

    def step_maintenance(self, dt: Dt):
        self.gnodes = self.graph.nodes

    def request(self, user: User, drop_node: str) -> tuple[Dt, float]:
        """
                Args:
                    user: User requesting a ride
                    drop_node:
                Returns: waiting time before pick-up
                """

        upos = user.position
        uid = user.id
        vehs = list(self.fleet.vehicles.keys())
        idle_service_dt = Dt(hours=24)
        occupied_service_dt = Dt(hours=24)
        while vehs:
            # Search for the nearest vehicle to the user
            veh_pos = np.array([self.fleet.vehicles[v].position for v in vehs])
            dist_vector = np.linalg.norm(veh_pos - upos, axis=1)
            nearest_veh_index = np.argmin(dist_vector)
            nearest_veh = vehs[nearest_veh_index]
            vehs.remove(nearest_veh)
            total_profit = 0
            choosen_veh = self.fleet.vehicles[nearest_veh]
            #            if not choosen_veh.is_full:
            if choosen_veh.is_empty:
                # Vehicle available if either stopped or repositioning, and has no activity planned afterwards
                available = True if ((choosen_veh.activity_type in [ActivityType.STOP, ActivityType.REPOSITIONING]) and (
                    not choosen_veh.activities)) else False
                if available:
                    # Compute pick-up path and cost from end of current activity
                    veh_last_node = choosen_veh.activity.node if not choosen_veh.activities else \
                        choosen_veh.activities[-1].node
                    veh_path_idle, cost_idle = dijkstra(self.graph, veh_last_node, user.current_node, 'travel_time',
                                              {self.layer.id: self.id}, {self.layer.id})
                    # If vehicle cannot reach user, skip and consider next vehicle
                    if cost_idle == float('inf'):
                        continue
                    len_path_idle = 0           # idle distance in meters
                    for i in range(len(veh_path_idle) - 1):
                        j = i + 1
                        len_path_idle += self.gnodes[veh_path_idle[i]].adj[veh_path_idle[j]].length

                    #print("\n")
                    #print(uid)
                    #print("Idle distance info:")
                    #print(cost_idle)
                    #print(len_path_idle)

                    ##############################
                    veh_path_service, cost_service = dijkstra(self.graph, user.current_node, user.path.nodes[-2], 'travel_time',
                                                        {self.layer.id: self.id}, {self.layer.id})
                    len_path_service = 0                # service distance in meters
                    for i in range(len(veh_path_service) - 1):
                        j = i + 1
                        len_path_service += self.gnodes[veh_path_service[i]].adj[veh_path_service[j]].length

                    #print("Service distance info:")
                    #print(cost_service)
                    #print(len_path_service)
                    ###############################
                    ##### per km charge:
                    driver_profit = (len_path_service * self.service_km_profit) / 1000
                    expenses_per_km = ((len_path_idle + len_path_service) * self.expenses_per_km) / 1000
                    idle_charge = (len_path_idle * self.idle_km_or_h_charge) / 1000

                    total_profit = max(driver_profit, self.min_trip_price) - expenses_per_km - idle_charge

                    ##### per hour charge:
                    #total_profit = self.matching_profit + (len_path_service * self.service_km_profit) / 1000 - \
                    #               ((len_path_idle + len_path_service) * self.expenses_per_km) / 1000 - \
                    #               (cost_idle * self.idle_km_or_h_charge) / 3600

                    threshold = ((cost_idle + cost_service) * self.driver_hour_min_payment) / 3600

                    if total_profit >= threshold:

                        # idle_service_dt = Dt(seconds=len_path / choosen_veh.speed)
                        idle_service_dt = Dt(seconds=cost_idle)  # idle time (time needed to pickup a user)
                        self._cache_request_vehicles[uid] = choosen_veh, veh_path_idle
                        break
                    else:
                        continue
        return idle_service_dt, total_profit

    def profit_update(self, user: User, driver_profit_per_trip: float):
        veh, veh_path = self._cache_request_vehicles[user.id]
        veh.trip_counter_update()
        veh.driver_profit_update(driver_profit_per_trip)

    def matching(self, user: User, drop_node: str):
        veh, veh_path = self._cache_request_vehicles[user.id]
        upath = list(user.path.nodes)
        upath = upath[upath.index(user._current_node):upath.index(drop_node) + 1]
        user_path = self.construct_veh_path(upath)
        veh_path = self.construct_veh_path(veh_path)
        activities = [
            VehicleActivityPickup(node=user._current_node,
                                  path=veh_path,
                                  user=user),
            VehicleActivityServing(node=drop_node,
                                   path=user_path,
                                   user=user)
        ]

        veh.add_activities(activities)
        user.set_state_waiting_vehicle()

        if veh.activity_type is ActivityType.STOP:
            veh.activity.is_done = True

    def launch_matching(self, new_users, user_flow, decision_model, dt):
        """
                Method that launch passenger-vehicles matching, through 1. requesting and 2. matching.
                Returns: empty list # TODO - should be cleaned

                """
        # refuse_user = list()

        if self._counter_matching == self._dt_matching:
            self._counter_matching = 0

            for uid, (user, drop_node) in list(self._user_buffer.items()):
                # User makes service request
                service_dt, driver_profit_per_trip = self.request(user, drop_node)

                if user.pickup_dt[self.id] > service_dt:
                    # If pick-up time is below passengers' waiting tolerance
                    # Match user with vehicle
                    self.matching(user, drop_node)

                    self.profit_update(user, driver_profit_per_trip)
                    # Remove user from list of users waiting to be matched
                    self._user_buffer.pop(uid)
                else:
                    # If pick-up time exceeds passengers' waiting tolerance
                    log.info(f"{uid} refused {self.id} offer (predicted pickup time too long)")
                    #user.set_state_stop()
                    #user.notify(self._tcurrent)
                    #refuse_user.append(user)
                self._cache_request_vehicles = dict()

            #self._user_buffer = dict()
            # NB: we clean _user_buffer here because answer provided by the mobility
            #     service should be YES I match with you or No I refuse you, but not
            #     let's wait the next timestep to see if I can find a vehicle for you
            #     Mob service has only one chance to propose a match to the user,
            #     except if user request the service again
        else:
            self._counter_matching += 1

        return list()  # refuse_user        # list of refused users?

    def __dump__(self):
        return {"TYPE": ".".join([RideHailingServiceIdleCharge.__module__, RideHailingServiceIdleCharge.__name__]),
                "DT_MATCHING": self._dt_matching,
                "VEH_CAPACITY": self._veh_capacity,
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data["DT_MATCHING"], data["VEH_CAPACITY"])
        return new_obj


class RideHailing_Utilization_Rate_Charge1(AbstractMobilityService):        # for each trip of each vehicle

    instances = []

    def __init__(self,
                 _id: str,
                 dt_matching: int,
                 dt_step_maintenance: int = 0):
        super(RideHailing_Utilization_Rate_Charge1, self).__init__(_id, 1, dt_matching, dt_step_maintenance)

        self.__class__.instances.append(self)
        self.gnodes = dict()
        self.nb_of_users_counter = 0
        self.refused_users_counter = 0
        self.max_pickup_dist = 2000                # maximum tolerable pickup distance for a driver
        self.max_pickup_time = Time("00:10:00")    # max tolerable pickup time for a driver
        self.cancellation_mode = 0                 #

        ####### Profits ans costs ###########

        self.idle_proportion_threshold = 0.1

        self.minimum_profit = 5
        self.service_km_profit = 1

        self.expenses_per_km = 0.15     # gaz + insurance + depreciation price
        self.extra_idle_km_charge = 2

        self.driver_hour_min_payment = 15

    def create_waiting_vehicle(self, node: str):
        assert node in self.graph.nodes
        new_veh = self.fleet.create_vehicle(node,
                                            capacity=self._veh_capacity,
                                            activities=[VehicleActivityStop(node=node)])
        new_veh.set_position(self.graph.nodes[node].position)

        if self._observer is not None:
            new_veh.attach(self._observer)

    def step_maintenance(self, dt: Dt):
        self.gnodes = self.graph.nodes

    def request(self, user: User, drop_node: str) -> tuple[Dt, float]:
        """
                Args:
                    user: User requesting a ride
                    drop_node:
                Returns: waiting time before pick-up
                """

        upos = user.position
        uid = user.id
        vehs = list(self.fleet.vehicles.keys())
        idle_service_dt = Dt(hours=24)
        occupied_service_dt = Dt(hours=24)
        while vehs:
            # Search for the nearest vehicle to the user
            veh_pos = np.array([self.fleet.vehicles[v].position for v in vehs])
            dist_vector = np.linalg.norm(veh_pos - upos, axis=1)
            nearest_veh_index = np.argmin(dist_vector)
            nearest_veh = vehs[nearest_veh_index]
            vehs.remove(nearest_veh)

            choosen_veh = self.fleet.vehicles[nearest_veh]
            #            if not choosen_veh.is_full:
            if choosen_veh.is_empty:
                # Vehicle available if either stopped or repositioning, and has no activity planned afterwards
                available = True if ((choosen_veh.activity_type in [ActivityType.STOP, ActivityType.REPOSITIONING]) and (
                    not choosen_veh.activities)) else False
                if available:
                    # Compute pick-up path and cost from end of current activity
                    veh_last_node = choosen_veh.activity.node if not choosen_veh.activities else \
                        choosen_veh.activities[-1].node
                    veh_path_idle, cost_idle = dijkstra(self.graph, veh_last_node, user.current_node, 'travel_time',
                                              {self.layer.id: self.id}, {self.layer.id})
                    # If vehicle cannot reach user, skip and consider next vehicle
                    if cost_idle == float('inf'):
                        continue
                    len_path_idle = 0           # idle distance in meters
                    for i in range(len(veh_path_idle) - 1):
                        j = i + 1
                        len_path_idle += self.gnodes[veh_path_idle[i]].adj[veh_path_idle[j]].length

                    ##############################
                    veh_path_service, cost_service = dijkstra(self.graph, user.current_node, user.path.nodes[-2], 'travel_time',
                                                        {self.layer.id: self.id}, {self.layer.id})
                    len_path_service = 0                # service distance in meters
                    for i in range(len(veh_path_service) - 1):
                        j = i + 1
                        len_path_service += self.gnodes[veh_path_service[i]].adj[veh_path_service[j]].length

                    ###############################
                    ##### extra idle km charge:
                    profit = 0
                    if (len_path_service * self.service_km_profit) / 1000 >= self.minimum_profit:
                        profit = (len_path_service * self.service_km_profit) / 1000
                    if (len_path_service * self.service_km_profit) / 1000 < self.minimum_profit:
                        profit = self.minimum_profit
                    if len_path_idle / len_path_service <= self.idle_proportion_threshold:
                        total_profit = profit - \
                                       ((len_path_idle + len_path_service) * self.expenses_per_km) / 1000

                    if len_path_idle / len_path_service > self.idle_proportion_threshold:
                        total_profit = profit - \
                                       ((len_path_idle + len_path_service) * self.expenses_per_km) / 1000 - \
                                       ((len_path_idle - len_path_service * self.idle_proportion_threshold) * self.extra_idle_km_charge) / 1000

                    threshold = ((cost_idle + cost_service) * self.driver_hour_min_payment) / 3600

                    if total_profit >= threshold:

                        # idle_service_dt = Dt(seconds=len_path / choosen_veh.speed)
                        idle_service_dt = Dt(seconds=cost_idle)  # idle time (time needed to pickup a user)
                        self._cache_request_vehicles[uid] = choosen_veh, veh_path_idle
                        break
                    else:
                        continue
        return idle_service_dt, total_profit

    def profit_update(self, user: User, driver_profit_per_trip: float):
        veh, veh_path = self._cache_request_vehicles[user.id]
        veh.trip_counter_update()
        veh.driver_profit_update(driver_profit_per_trip)

    def matching(self, user: User, drop_node: str):
        veh, veh_path = self._cache_request_vehicles[user.id]
        upath = list(user.path.nodes)
        upath = upath[upath.index(user._current_node):upath.index(drop_node) + 1]
        user_path = self.construct_veh_path(upath)
        veh_path = self.construct_veh_path(veh_path)
        activities = [
            VehicleActivityPickup(node=user._current_node,
                                  path=veh_path,
                                  user=user),
            VehicleActivityServing(node=drop_node,
                                   path=user_path,
                                   user=user)
        ]

        veh.add_activities(activities)
        user.set_state_waiting_vehicle()

        if veh.activity_type is ActivityType.STOP:
            veh.activity.is_done = True

    def launch_matching(self):
        """
                Method that launch passenger-vehicles matching, through 1. requesting and 2. matching.
                Returns: empty list # TODO - should be cleaned

                """
        # refuse_user = list()

        if self._counter_matching == self._dt_matching:
            self._counter_matching = 0

            for uid, (user, drop_node) in list(self._user_buffer.items()):
                # User makes service request
                service_dt, driver_profit_per_trip = self.request(user, drop_node)

                if user.pickup_dt[self.id] > service_dt:
                    # If pick-up time is below passengers' waiting tolerance
                    # Match user with vehicle
                    self.matching(user, drop_node)

                    self.profit_update(user, driver_profit_per_trip)
                    # Remove user from list of users waiting to be matched
                    self._user_buffer.pop(uid)
                else:
                    # If pick-up time exceeds passengers' waiting tolerance
                    log.info(f"{uid} refused {self.id} offer (predicted pickup time too long)")
                    #user.set_state_stop()
                    #user.notify(self._tcurrent)
                    #refuse_user.append(user)
                self._cache_request_vehicles = dict()

            #self._user_buffer = dict()
            # NB: we clean _user_buffer here because answer provided by the mobility
            #     service should be YES I match with you or No I refuse you, but not
            #     let's wait the next timestep to see if I can find a vehicle for you
            #     Mob service has only one chance to propose a match to the user,
            #     except if user request the service again
        else:
            self._counter_matching += 1

        return list()  # refuse_user        # list of refused users?

    def __dump__(self):
        return {"TYPE": ".".join([RideHailing_Utilization_Rate_Charge1.__module__, RideHailing_Utilization_Rate_Charge1.__name__]),
                "DT_MATCHING": self._dt_matching,
                "VEH_CAPACITY": self._veh_capacity,
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data["DT_MATCHING"], data["VEH_CAPACITY"])
        return new_obj


class RideHailing_Utilization_Rate_Charge2(AbstractMobilityService):        # for the total distance traveled by a vehicle during the day

    instances = []

    def __init__(self,
                 _id: str,
                 dt_matching: int,
                 dt_step_maintenance: int = 0):
        super(RideHailing_Utilization_Rate_Charge2, self).__init__(_id, 1, dt_matching, dt_step_maintenance)

        self.__class__.instances.append(self)
        self.gnodes = dict()
        self.nb_of_users_counter = 0
        self.refused_users_counter = 0
        self.max_pickup_dist = 2000                # maximum tolerable pickup distance for a driver
        self.max_pickup_time = Time("00:10:00")    # max tolerable pickup time for a driver
        self.cancellation_mode = 0                 #

        ####### Profits ans costs ###########

        self.idle_proportion_threshold = 0.1

        self.minimum_profit = 5
        self.service_km_profit = 1

        self.expenses_per_km = 0.15     # gaz + insurance + depreciation price
        self.extra_idle_km_charge = 2

        self.driver_hour_min_payment = 15

    def create_waiting_vehicle(self, node: str):
        assert node in self.graph.nodes
        new_veh = self.fleet.create_vehicle(node,
                                            capacity=self._veh_capacity,
                                            activities=[VehicleActivityStop(node=node)])
        new_veh.set_position(self.graph.nodes[node].position)

        if self._observer is not None:
            new_veh.attach(self._observer)

    def step_maintenance(self, dt: Dt):
        self.gnodes = self.graph.nodes

    def request(self, user: User, drop_node: str) -> tuple[Dt, float]:
        """
                Args:
                    user: User requesting a ride
                    drop_node:
                Returns: waiting time before pick-up
                """

        upos = user.position
        uid = user.id
        vehs = list(self.fleet.vehicles.keys())
        idle_service_dt = Dt(hours=24)
        occupied_service_dt = Dt(hours=24)
        while vehs:
            # Search for the nearest vehicle to the user
            veh_pos = np.array([self.fleet.vehicles[v].position for v in vehs])
            dist_vector = np.linalg.norm(veh_pos - upos, axis=1)
            nearest_veh_index = np.argmin(dist_vector)
            nearest_veh = vehs[nearest_veh_index]
            vehs.remove(nearest_veh)

            choosen_veh = self.fleet.vehicles[nearest_veh]
            #            if not choosen_veh.is_full:
            if choosen_veh.is_empty:
                # Vehicle available if either stopped or repositioning, and has no activity planned afterwards
                available = True if ((choosen_veh.activity_type in [ActivityType.STOP, ActivityType.REPOSITIONING]) and (
                    not choosen_veh.activities)) else False
                if available:
                    # Compute pick-up path and cost from end of current activity
                    veh_last_node = choosen_veh.activity.node if not choosen_veh.activities else \
                        choosen_veh.activities[-1].node
                    veh_path_idle, cost_idle = dijkstra(self.graph, veh_last_node, user.current_node, 'travel_time',
                                              {self.layer.id: self.id}, {self.layer.id})
                    # If vehicle cannot reach user, skip and consider next vehicle
                    if cost_idle == float('inf'):
                        continue
                    len_path_idle = 0           # idle distance in meters
                    for i in range(len(veh_path_idle) - 1):
                        j = i + 1
                        len_path_idle += self.gnodes[veh_path_idle[i]].adj[veh_path_idle[j]].length

                    ##############################
                    veh_path_service, cost_service = dijkstra(self.graph, user.current_node, user.path.nodes[-2], 'travel_time',
                                                        {self.layer.id: self.id}, {self.layer.id})
                    len_path_service = 0                # service distance in meters
                    for i in range(len(veh_path_service) - 1):
                        j = i + 1
                        len_path_service += self.gnodes[veh_path_service[i]].adj[veh_path_service[j]].length

                    ###############################
                    ##### extra idle km charge for the total car travel dist:
                    profit = 0
                    if (len_path_service * self.service_km_profit) / 1000 >= self.minimum_profit:
                        profit = (len_path_service * self.service_km_profit) / 1000
                    if (len_path_service * self.service_km_profit) / 1000 < self.minimum_profit:
                        profit = self.minimum_profit
                    if ((choosen_veh.pickup_distance + len_path_idle) / (choosen_veh.service_distance + len_path_service)) \
                            <= self.idle_proportion_threshold:
                        total_profit = profit - \
                                       ((len_path_idle + len_path_service) * self.expenses_per_km) / 1000

                    if ((choosen_veh.pickup_distance + len_path_idle) / (choosen_veh.service_distance + len_path_service)) \
                            > self.idle_proportion_threshold:
                        total_profit = profit - \
                                       ((len_path_idle + len_path_service) * self.expenses_per_km) / 1000 - \
                                       (((choosen_veh.pickup_distance + len_path_idle)                                  # look for the explanation in my copybook
                                         - (choosen_veh.service_distance + len_path_service) * self.idle_proportion_threshold)
                                        * self.extra_idle_km_charge) / 1000

                    threshold = ((cost_idle + cost_service) * self.driver_hour_min_payment) / 3600

                    if total_profit >= threshold:

                        # idle_service_dt = Dt(seconds=len_path / choosen_veh.speed)
                        idle_service_dt = Dt(seconds=cost_idle)  # idle time (time needed to pickup a user)
                        self._cache_request_vehicles[uid] = choosen_veh, veh_path_idle
                        break
                    else:
                        continue
        return idle_service_dt, total_profit

    def profit_update(self, user: User, driver_profit_per_trip: float):
        veh, veh_path = self._cache_request_vehicles[user.id]
        veh.trip_counter_update()
        veh.driver_profit_update(driver_profit_per_trip)

    def matching(self, user: User, drop_node: str):
        veh, veh_path = self._cache_request_vehicles[user.id]
        upath = list(user.path.nodes)
        upath = upath[upath.index(user._current_node):upath.index(drop_node) + 1]
        user_path = self.construct_veh_path(upath)
        veh_path = self.construct_veh_path(veh_path)
        activities = [
            VehicleActivityPickup(node=user._current_node,
                                  path=veh_path,
                                  user=user),
            VehicleActivityServing(node=drop_node,
                                   path=user_path,
                                   user=user)
        ]

        veh.add_activities(activities)
        user.set_state_waiting_vehicle()

        if veh.activity_type is ActivityType.STOP:
            veh.activity.is_done = True

    def launch_matching(self):
        """
                Method that launch passenger-vehicles matching, through 1. requesting and 2. matching.
                Returns: empty list # TODO - should be cleaned

                """
        # refuse_user = list()

        if self._counter_matching == self._dt_matching:
            self._counter_matching = 0

            for uid, (user, drop_node) in list(self._user_buffer.items()):
                # User makes service request
                service_dt, driver_profit_per_trip = self.request(user, drop_node)

                if user.pickup_dt[self.id] > service_dt:
                    # If pick-up time is below passengers' waiting tolerance
                    # Match user with vehicle
                    self.matching(user, drop_node)

                    self.profit_update(user, driver_profit_per_trip)
                    # Remove user from list of users waiting to be matched
                    self._user_buffer.pop(uid)
                else:
                    # If pick-up time exceeds passengers' waiting tolerance
                    log.info(f"{uid} refused {self.id} offer (predicted pickup time too long)")
                    #user.set_state_stop()
                    #user.notify(self._tcurrent)
                    #refuse_user.append(user)
                self._cache_request_vehicles = dict()

            #self._user_buffer = dict()
            # NB: we clean _user_buffer here because answer provided by the mobility
            #     service should be YES I match with you or No I refuse you, but not
            #     let's wait the next timestep to see if I can find a vehicle for you
            #     Mob service has only one chance to propose a match to the user,
            #     except if user request the service again
        else:
            self._counter_matching += 1

        return list()  # refuse_user        # list of refused users?

    def __dump__(self):
        return {"TYPE": ".".join([RideHailing_Utilization_Rate_Charge2.__module__, RideHailing_Utilization_Rate_Charge2.__name__]),
                "DT_MATCHING": self._dt_matching,
                "VEH_CAPACITY": self._veh_capacity,
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data["DT_MATCHING"], data["VEH_CAPACITY"])
        return new_obj


class RideHailingIndivForecast(AbstractMobilityService):        # Individual with forecast + idle distance charge

    instances = []

    def __init__(self,
                 _id: str,
                 dt_matching: int,
                 dt_step_maintenance: int = 0):
        super(RideHailingIndivForecast, self).__init__(_id, 1, dt_matching, dt_step_maintenance)

        self.__class__.instances.append(self)
        self.gnodes = dict()
        self.nb_of_users_counter = 0
        self.refused_users_counter = 0
        self.max_pickup_dist = 2000                # maximum tolerable pickup distance for a driver
        self.max_pickup_time = Time("00:10:00")    # max tolerable pickup time for a driver
        self.cancellation_mode = 0                 #

        ####### Profits and costs ###########

        self.min_trip_price = 7
        self.service_km_profit = 1.7
        self.expenses_per_km = 0.3     # gaz + insurance + depreciation price
        self.idle_km_or_h_charge = 0.4
        self.driver_hour_min_payment = 18
        self.company_fee = 0.25          # percentage of profit that company takes from driver
        self.bonus = 1
        self.penalty = 1

    def create_waiting_vehicle(self, node: str):
        assert node in self.graph.nodes
        new_veh = self.fleet.create_vehicle(node,
                                            capacity=self._veh_capacity,
                                            activities=[VehicleActivityStop(node=node)])
        new_veh.set_position(self.graph.nodes[node].position)

        if self._observer is not None:
            new_veh.attach(self._observer)

    def step_maintenance(self, dt: Dt):
        self.gnodes = self.graph.nodes

    def request(self, user: User, drop_node: str) -> tuple[Dt, float]:
        """
                Args:
                    user: User requesting a ride
                    drop_node:
                Returns: waiting time before pick-up
                """

        upos = user.position
        uid = user.id
        vehs = list(self.fleet.vehicles.keys())
        idle_service_dt = Dt(hours=24)
        occupied_service_dt = Dt(hours=24)
        while vehs:
            # Search for the nearest vehicle to the user
            veh_pos = np.array([self.fleet.vehicles[v].position for v in vehs])
            dist_vector = np.linalg.norm(veh_pos - upos, axis=1)
            nearest_veh_index = np.argmin(dist_vector)
            nearest_veh = vehs[nearest_veh_index]
            vehs.remove(nearest_veh)

            choosen_veh = self.fleet.vehicles[nearest_veh]
            #            if not choosen_veh.is_full:
            if choosen_veh.is_empty:
                # Vehicle available if either stopped or repositioning, and has no activity planned afterwards
                available = True if ((choosen_veh.activity_type in [ActivityType.STOP, ActivityType.REPOSITIONING]) and (
                    not choosen_veh.activities)) else False
                if available:
                    # Compute pick-up path and cost from end of current activity
                    veh_last_node = choosen_veh.activity.node if not choosen_veh.activities else \
                        choosen_veh.activities[-1].node
                    veh_path_idle, cost_idle = dijkstra(self.graph, veh_last_node, user.current_node, 'travel_time',
                                              {self.layer.id: self.id}, {self.layer.id})
                    # If vehicle cannot reach user, skip and consider next vehicle
                    if cost_idle == float('inf'):
                        continue
                    len_path_idle = 0           # idle distance in meters
                    for i in range(len(veh_path_idle) - 1):
                        j = i + 1
                        len_path_idle += self.gnodes[veh_path_idle[i]].adj[veh_path_idle[j]].length

                    #print("\n")
                    #print(uid)
                    #print("Idle distance info:")
                    #print(cost_idle)
                    #print(len_path_idle)

                    ##############################
                    veh_path_service, cost_service = dijkstra(self.graph, user.current_node, user.path.nodes[-2], 'travel_time',
                                                        {self.layer.id: self.id}, {self.layer.id})
                    len_path_service = 0                # service distance in meters
                    for i in range(len(veh_path_service) - 1):
                        j = i + 1
                        len_path_service += self.gnodes[veh_path_service[i]].adj[veh_path_service[j]].length

                    #print("Service distance info:")
                    #print(cost_service)
                    #print(len_path_service)
                    ###############################
                    ##### per km charge:
                    min_price = self.min_trip_price
                    driver_profit = (len_path_service * self.service_km_profit) / 1000




                    expenses_per_km = ((len_path_idle + len_path_service) * self.expenses_per_km) / 1000
                    idle_charge = (len_path_idle * self.idle_km_or_h_charge) / 1000

                    total_profit = max(driver_profit, min_price) - expenses_per_km - idle_charge

                    ##### per hour charge:
                    #total_profit = self.matching_profit + (len_path_service * self.service_km_profit) / 1000 - \
                    #               ((len_path_idle + len_path_service) * self.expenses_per_km) / 1000 - \
                    #               (cost_idle * self.idle_km_or_h_charge) / 3600
                    threshold = ((cost_idle + cost_service) * self.driver_hour_min_payment) / 3600

                    if user.dest_region_demand_level[0] == '1':
                        threshold = threshold - self.bonus

                    if user.dest_region_demand_level[0] == '-1':
                        threshold = threshold + self.penalty

                    else:
                        threshold = threshold


                    if total_profit >= threshold:

                        # idle_service_dt = Dt(seconds=len_path / choosen_veh.speed)
                        idle_service_dt = Dt(seconds=cost_idle)  # idle time (time needed to pickup a user)
                        self._cache_request_vehicles[uid] = choosen_veh, veh_path_idle
                        break
                    else:
                        continue
        return idle_service_dt, total_profit

    def matching(self, user: User, drop_node: str):
        veh, veh_path = self._cache_request_vehicles[user.id]
        upath = list(user.path.nodes)
        upath = upath[upath.index(user._current_node):upath.index(drop_node) + 1]
        user_path = self.construct_veh_path(upath)
        veh_path = self.construct_veh_path(veh_path)
        activities = [
            VehicleActivityPickup(node=user._current_node,
                                  path=veh_path,
                                  user=user),
            VehicleActivityServing(node=drop_node,
                                   path=user_path,
                                   user=user)
        ]

        veh.add_activities(activities)
        user.set_state_waiting_vehicle()

        if veh.activity_type is ActivityType.STOP:
            veh.activity.is_done = True

    def profit_update(self, user: User, driver_profit_per_trip: float):
        veh, veh_path = self._cache_request_vehicles[user.id]
        veh.trip_counter_update()
        veh.driver_profit_update(driver_profit_per_trip)

    def launch_matching(self):
        """
                Method that launch passenger-vehicles matching, through 1. requesting and 2. matching.
                Returns: empty list # TODO - should be cleaned

                """
        # refuse_user = list()

        if self._counter_matching == self._dt_matching:
            self._counter_matching = 0

            for uid, (user, drop_node) in list(self._user_buffer.items()):
                # User makes service request
                service_dt, driver_profit_per_trip = self.request(user, drop_node)

                if user.pickup_dt[self.id] > service_dt:
                    # If pick-up time is below passengers' waiting tolerance
                    # Match user with vehicle
                    self.matching(user, drop_node)
                    self.profit_update(user, driver_profit_per_trip)

                    # Remove user from list of users waiting to be matched
                    self._user_buffer.pop(uid)
                else:
                    # If pick-up time exceeds passengers' waiting tolerance
                    log.info(f"{uid} refused {self.id} offer (predicted pickup time too long)")
                    #user.set_state_stop()
                    #user.notify(self._tcurrent)
                    #refuse_user.append(user)
                self._cache_request_vehicles = dict()

            #self._user_buffer = dict()
            # NB: we clean _user_buffer here because answer provided by the mobility
            #     service should be YES I match with you or No I refuse you, but not
            #     let's wait the next timestep to see if I can find a vehicle for you
            #     Mob service has only one chance to propose a match to the user,
            #     except if user request the service again
        else:
            self._counter_matching += 1

        return list()  # refuse_user        # list of refused users?

    def __dump__(self):
        return {"TYPE": ".".join([RideHailingIndivForecast.__module__, RideHailingIndivForecast.__name__]),
                "DT_MATCHING": self._dt_matching,
                "VEH_CAPACITY": self._veh_capacity,
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data["DT_MATCHING"], data["VEH_CAPACITY"])
        return new_obj

