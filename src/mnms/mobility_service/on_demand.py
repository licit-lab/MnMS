from typing import Tuple, Dict

import numpy as np

from hipop.shortest_path import dijkstra

from mnms import create_logger
from mnms.demand import User
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.time import Dt
from mnms.tools.exceptions import PathNotFound
from mnms.vehicles.veh_type import VehicleState, VehicleActivityServing, VehicleActivityStop, \
    VehicleActivityPickup, VehicleActivityRepositioning

log = create_logger(__name__)


class OnDemandMobilityService(AbstractMobilityService):
    def __init__(self,
                 _id: str,
                 dt_matching: int,
                 dt_step_maintenance: int = 0):
        super(OnDemandMobilityService, self).__init__(_id, 1, dt_matching, dt_step_maintenance)

        self.gnodes = dict()

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

    def request(self, user: User, drop_node: str) -> Dt:
        """

        Args:
            user: User requesting a ride
            drop_node:

        Returns: waiting time before pick-up

        """

        upos = user.position
        uid = user.id
        vehs = list(self.fleet.vehicles.keys())

        service_dt = Dt(hours=24)

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
                available = True if ((choosen_veh.state in [VehicleState.STOP, VehicleState.REPOSITIONING]) and (not choosen_veh.activities)) else False
                if available:
                    # Compute pick-up path and cost from end of current activity
                    veh_last_node = choosen_veh.activity.node if not choosen_veh.activities else \
                    choosen_veh.activities[-1].node
                    veh_path, cost = dijkstra(self.graph, veh_last_node, user.current_node, 'travel_time', {self.layer.id: self.id}, {self.layer.id})
                    # If vehicle cannot reach user, skip and consider next vehicle
                    if cost == float('inf'):
                        continue
                        # raise PathNotFound(choosen_veh._current_node, user.current_node)

                    len_path = 0
                    for i in range(len(veh_path) - 1):
                        j = i + 1
                        len_path += self.gnodes[veh_path[i]].adj[veh_path[j]].length

                    service_dt = Dt(seconds=cost)
                    self._cache_request_vehicles[uid] = choosen_veh, veh_path
                    break

        return service_dt

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

        if veh.state is VehicleState.STOP:
            veh.activity.is_done = True

    def __dump__(self):
        return {"TYPE": ".".join([OnDemandMobilityService.__module__, OnDemandMobilityService.__name__]),
                "DT_MATCHING": self._dt_matching,
                "VEH_CAPACITY": self._veh_capacity,
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data["DT_MATCHING"], data["VEH_CAPACITY"])
        return new_obj


class OnDemandDepotMobilityService(AbstractMobilityService):
    def __init__(self,
                 _id: str,
                 dt_matching: int,
                 dt_step_maintenance: int = 0):
        """
        Class for modelling an on-demand mobility service with depots

        Args:
            depot: the list of depot (defined by location -a node-, the waiting vehicles and the capacity)
        """
        super(OnDemandDepotMobilityService, self).__init__(_id, 1, dt_matching, dt_step_maintenance)
        self.gnodes = None
        self.depot = dict()

    def _create_waiting_vehicle(self, node: str):
        assert node in self.graph.nodes
        new_veh = self.fleet.create_vehicle(node,
                                            capacity=self._veh_capacity,
                                            activities=[VehicleActivityStop(node=node)])
        new_veh.set_position(self.graph.nodes[node].position)

        if self._observer is not None:
            new_veh.attach(self._observer)

        return new_veh

    def add_depot(self, node: str, capacity: int):
        self.depot[node] = {"capacity": capacity,
                            "vehicles": set()}

        for _ in range(capacity):
            new_veh = self._create_waiting_vehicle(node)
            self.depot[node]["vehicles"].add(new_veh.id)

    def is_depot_full(self, node: str):
        return self.depot[node]["capacity"] == len(self.depot[node]["vehicles"])

    def step_maintenance(self, dt: Dt):
        self.gnodes = self.graph.nodes

        depot = list(self.depot.keys())
        depot_pos = np.array([self.gnodes[d].position for d in self.depot.keys()])

        for veh in self.fleet.vehicles.values():
            if veh.state is VehicleState.STOP:
                if veh._current_node not in self.depot:
                    veh_position = veh.position
                    dist_vector = np.linalg.norm(depot_pos - veh_position, axis=1)
                    sorted_ind = np.argsort(dist_vector)

                    nearest_depot = None
                    for nearest_depot_ind in sorted_ind:
                        current_depot = depot[nearest_depot_ind]
                        if not self.is_depot_full(current_depot):
                            nearest_depot = current_depot
                            break

                    veh_path, cost = dijkstra(self.graph,
                                              veh._current_node,
                                              nearest_depot,
                                              'travel_time',
                                              {self.layer.id: self.id,
                                               "TRANSIT": "WALK"},
                                              {self.layer.id})
                    if cost == float('inf'):
                        raise PathNotFound(veh._current_node, depot)

                    veh_path = self.construct_veh_path(veh_path)
                    repositioning = VehicleActivityRepositioning(node=nearest_depot,
                                                                 path=veh_path)
                    veh.activity.is_done = True
                    veh.add_activities([repositioning])
                else:
                    self.depot[veh._current_node]["vehicles"].add(veh.id)

    def request(self, user: User, drop_node: str) -> Dt:
        """

        Args:
            user: User requesting a ride
            drop_node:

        Returns: waiting time before pick-up

        """

        service_dt = Dt(hours=24)
        upos = user.position

        vehs = list(self.fleet.vehicles.keys())

        while vehs:
            veh_pos = np.array([self.fleet.vehicles[v].position for v in vehs])
            dist_vector = np.linalg.norm(veh_pos - upos, axis=1)
            nearest_veh_index = np.argmin(dist_vector)
            nearest_veh = vehs[nearest_veh_index]

            vehs.remove(nearest_veh)
            choosen_veh = self.fleet.vehicles[nearest_veh]
            #if not choosen_veh.is_full:
            if choosen_veh.is_empty:
                # Vehicle available if either stopped or repositioning, and has no activity planned afterwards
                available = True if ((choosen_veh.state in [VehicleState.STOP, VehicleState.REPOSITIONING]) and (not choosen_veh.activities)) else False
                if available:
                    # Compute pick-up path and cost from end of current activity
                    veh_last_node = choosen_veh.activity.node if not choosen_veh.activities else \
                    choosen_veh.activities[-1].node
                    veh_path, cost = dijkstra(self.graph,
                                              veh_last_node,
                                              user.current_node,
                                              'travel_time',
                                              {self.layer.id: self.id,
                                               "TRANSIT": "WALK"},
                                              {self.layer.id})
                    # If vehicle cannot reach user, skip and consider next vehicle
                    if cost == float('inf'):
                        continue

                    len_path = 0
                    for i in range(len(veh_path) - 1):
                        j = i + 1
                        len_path += self.gnodes[veh_path[i]].adj[veh_path[j]].length

                    service_dt = Dt(seconds=cost)
                    self._cache_request_vehicles[user.id] = choosen_veh, veh_path
                    break

        return service_dt

    def matching(self, user: User, drop_node: str):
        veh, veh_path = self._cache_request_vehicles[user.id]
        upath = list(user.path.nodes)
        upath = upath[upath.index(user._current_node):upath.index(drop_node) + 1]

        user_path = self.construct_veh_path(upath)
        veh_path = self.construct_veh_path(veh_path)

        if veh_path:
            pickup = VehicleActivityPickup(node=user._current_node,
                                           path=veh_path,
                                           user=user)
        else:
            pickup = VehicleActivityPickup(node=user._current_node,
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
        user.set_state_waiting_vehicle()

        if veh.state is VehicleState.STOP:
            veh.activity.is_done = True
            if veh._current_node in self.depot:
                self.depot[veh._current_node]["vehicles"].remove(veh.id)

    def __dump__(self):
        return {"TYPE": ".".join([OnDemandMobilityService.__module__, OnDemandMobilityService.__name__]),
                "DT_MATCHING": self._dt_matching,
                "VEH_CAPACITY": self._veh_capacity,
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data["DT_MATCHING"], data["VEH_CAPACITY"])
        return new_obj
