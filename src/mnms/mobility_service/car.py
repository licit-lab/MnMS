from random import sample
from typing import List, Tuple, Dict

import numpy as np

from hipop.shortest_path import dijkstra

from mnms import create_logger
from mnms.demand import User
from mnms.demand.horizon import AbstractDemandHorizon
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.time import Dt
from mnms.tools.exceptions import PathNotFound
from mnms.vehicles.veh_type import VehicleState, VehicleActivityServing, VehicleActivityStop, Vehicle, \
    VehicleActivityPickup, VehicleActivityRepositioning

log = create_logger(__name__)


class PersonalCarMobilityService(AbstractMobilityService):
    def __init__(self, _id: str = 'PersonalCar'):
        super(PersonalCarMobilityService, self).__init__(_id, veh_capacity=1, dt_matching=0, dt_periodic_maintenance=0)

    def matching(self, users: Dict[str, Tuple[User, str]]) -> List[str]:
        user_matched = list()
        for uid, (user, drop_node) in users.items():
            upath = list(user.path.nodes)
            upath = upath[upath.index(user._current_node):upath.index(drop_node)+1]
            veh_path = self._construct_veh_path(upath)
            new_veh = self.fleet.create_vehicle(upath[0],
                                                capacity=self._veh_capacity,
                                                activities=[VehicleActivityServing(node=user.destination,
                                                                                   path=veh_path,
                                                                                   user=user)])
            if self._observer is not None:
                new_veh.attach(self._observer)

            user_matched.append(uid)

        return user_matched

    def step_maintenance(self, dt: Dt):
        for veh in list(self.fleet.vehicles.values()):
            if veh.state is VehicleState.STOP:
                self.fleet.delete_vehicle(veh.id)

    def replanning(self):
        pass

    def rebalancing(self, next_demand: List[User], horizon: List[Vehicle]):
        pass

    def __dump__(self):
        return {"TYPE": ".".join([PersonalCarMobilityService.__module__, PersonalCarMobilityService.__name__]),
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'])
        return new_obj


class OnDemandCarMobilityService(AbstractMobilityService):
    def __init__(self,
                 _id: str,
                 dt_matching: int,
                 dt_step_maintenance: int = 0):
        super(OnDemandCarMobilityService, self).__init__(_id, 1, dt_matching, dt_step_maintenance)

    def create_waiting_vehicle(self, node: str):
        assert node in self.graph.nodes
        new_veh = self.fleet.create_vehicle(node,
                                            capacity=self._veh_capacity,
                                            activities=[VehicleActivityStop(node=node)])
        new_veh.set_position(self.graph_nodes[node].position)

        if self._observer is not None:
            new_veh.attach(self._observer)

    def matching(self, users: Dict[str, Tuple[User, str]]):
        user_matched = list()
        for uid, (user, drop_node) in users.items():
            # user.available_mobility_service = frozenset([self.id])

            upos = user.position
            upath = list(user.path.nodes)
            upath = upath[upath.index(user._current_node):upath.index(drop_node)+1]

            vehs = list(self.fleet.vehicles.keys())

            while vehs:
                veh_pos = np.array([self.fleet.vehicles[v].position for v in vehs])
                dist_vector = np.linalg.norm(veh_pos - upos, axis=1)
                nearest_veh_index = np.argmin(dist_vector)
                nearest_veh = vehs[nearest_veh_index]

                vehs.remove(nearest_veh)
                choosen_veh = self.fleet.vehicles[nearest_veh]
                if not choosen_veh.is_full:
                    if choosen_veh.is_empty:
                        veh_last_node = choosen_veh.activity.node if not choosen_veh.activities else choosen_veh.activities[-1].node
                        veh_path, cost = dijkstra(self.graph, veh_last_node, user.current_node, 'travel_time', set([self.layer.id]))
                        if cost == float('inf'):
                            raise PathNotFound(nearest_veh.origin, user.current_node)

                        user_path = self._construct_veh_path(upath)
                        veh_path = self._construct_veh_path(veh_path)
                        activities = [
                            VehicleActivityPickup(node=user._current_node,
                                                  path=veh_path,
                                                  user=user),
                            VehicleActivityServing(node=user.destination,
                                                   path=user_path,
                                                   user=user)
                        ]

                        choosen_veh.add_activities(activities)
                        user_matched.append(uid)
                        user.set_state_waiting_vehicle()

                        if choosen_veh.state is VehicleState.STOP:
                            choosen_veh.activity.is_done = True

                        continue

        return user_matched

    def __dump__(self):
        return {"TYPE": ".".join([OnDemandCarMobilityService.__module__, OnDemandCarMobilityService.__name__]),
                "DT_MATCHING": self._dt_matching,
                "VEH_CAPACITY": self._veh_capacity,
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data["DT_MATCHING"], data["VEH_CAPACITY"])
        return new_obj


class OnDemandCarDepotMobilityService(AbstractMobilityService):
    def __init__(self,
                 _id: str,
                 dt_matching: int,
                 dt_step_maintenance: int = 0):
        super(OnDemandCarDepotMobilityService, self).__init__(_id, 1, dt_matching, dt_step_maintenance)
        self.depot = dict()

    def _create_waiting_vehicle(self, node: str):
        assert node in self.graph.nodes
        new_veh = self.fleet.create_vehicle(node,
                                            capacity=self._veh_capacity,
                                            activities=[VehicleActivityStop(node=node)])
        new_veh.set_position(self.graph_nodes[node].position)

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
        depot = list(self.depot.keys())
        depot_pos = np.array([self.graph_nodes[d].position for d in self.depot.keys()])

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

                    veh_path, cost = dijkstra(self.graph, veh._current_node, nearest_depot, 'travel_time', {self.layer.id})
                    if cost == float('inf'):
                        raise PathNotFound(veh._current_node, depot)

                    veh_path = self._construct_veh_path(veh_path)
                    repositioning = VehicleActivityRepositioning(node=depot,
                                                                 path=veh_path)
                    veh.activity.is_done = True
                    veh.add_activities([repositioning])
                else:
                    self.depot[veh._current_node]["vehicles"].add(veh.id)

    def matching(self, users: Dict[str, Tuple[User, str]]):
        user_matched = list()
        for uid, (user, drop_node) in users.items():
            # user.available_mobility_service = frozenset([self.id])

            upos = user.position
            upath = list(user.path.nodes)
            upath = upath[upath.index(user._current_node):upath.index(drop_node)+1]

            vehs = list(self.fleet.vehicles.keys())

            while vehs:
                veh_pos = np.array([self.fleet.vehicles[v].position for v in vehs])
                dist_vector = np.linalg.norm(veh_pos - upos, axis=1)
                nearest_veh_index = np.argmin(dist_vector)
                nearest_veh = vehs[nearest_veh_index]

                vehs.remove(nearest_veh)
                choosen_veh = self.fleet.vehicles[nearest_veh]
                if not choosen_veh.is_full:
                    if choosen_veh.is_empty:
                        veh_last_node = choosen_veh.activity.node if not choosen_veh.activities else choosen_veh.activities[-1].node
                        veh_path, cost = dijkstra(self.graph, veh_last_node, user.current_node, 'travel_time', {self.layer.id})
                        if cost == float('inf'):
                            raise PathNotFound(nearest_veh.origin, user.current_node)

                        user_path = self._construct_veh_path(upath)
                        veh_path = self._construct_veh_path(veh_path)
                        activities = [
                            VehicleActivityPickup(node=user._current_node,
                                                  path=veh_path,
                                                  user=user),
                            VehicleActivityServing(node=user.destination,
                                                   path=user_path,
                                                   user=user)
                        ]

                        choosen_veh.add_activities(activities)
                        user_matched.append(uid)
                        user.set_state_waiting_vehicle()

                        if choosen_veh.state is VehicleState.STOP:
                            choosen_veh.activity.is_done = True
                            if choosen_veh._current_node in self.depot:
                                self.depot[choosen_veh._current_node]["vehicles"].remove(choosen_veh.id)

                        continue

        return user_matched

    def __dump__(self):
        return {"TYPE": ".".join([OnDemandCarMobilityService.__module__, OnDemandCarMobilityService.__name__]),
                "DT_MATCHING": self._dt_matching,
                "VEH_CAPACITY": self._veh_capacity,
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data["DT_MATCHING"], data["VEH_CAPACITY"])
        return new_obj