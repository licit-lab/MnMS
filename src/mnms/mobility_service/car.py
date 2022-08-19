from random import sample
from typing import List, Tuple, Dict, Optional

import numpy as np


from hipop.shortest_path import dijkstra

from mnms import create_logger
from mnms.demand import User
from mnms.demand.horizon import AbstractDemandHorizon
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.time import Dt, Time
from mnms.tools.exceptions import PathNotFound
from mnms.vehicles.veh_type import VehicleActivity, VehicleState, VehicleActivityServing, VehicleActivityStop, Vehicle

log = create_logger(__name__)


class PersonalCarMobilityService(AbstractMobilityService):
    def __init__(self, _id: str = 'PersonalCar', dt_matching=1):
        super(PersonalCarMobilityService, self).__init__(_id, dt_matching, veh_capacity=1)

    def matching(self, users: Dict[str, Tuple[User, str]]):

        user_matched = list()
        for uid, (user, drop_node) in users.items():
            upath = list(user.path.nodes)
            upath = upath[upath.index(user._current_node):upath.index(drop_node)+1]
            veh_path = self._construct_veh_path(upath)
            new_veh = self.fleet.create_vehicle(upath[0],
                                                capacity=self._veh_capacity,
                                                activities=[VehicleActivityServing(node=user.current_node,
                                                                                   path=veh_path,
                                                                                   user=user)])
            if self._observer is not None:
                new_veh.attach(self._observer)

            user_matched.append(uid)

        return user_matched

    def maintenance(self, dt: Dt):
        for veh in list(self.fleet.vehicles.values()):
            if veh.state is VehicleState.STOP:
                self.fleet.delete_vehicle(veh.id)

    def replaning(self):
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
                 demand_horizon: AbstractDemandHorizon):
        super(OnDemandCarMobilityService, self).__init__(_id, dt_matching, demand_horizon)
        self._is_duplicate = True
        self.depots = {}
        self._waiting_vehicle = dict()

    def _prefix(self, id:str):
        return f"{self.id}_{id}"

    def random_distribution_vehicles(self, n_veh:int):
        for n in sample(list(self.graph.nodes), n_veh):
            veh = self.fleet.create_waiting_vehicle(n, None, [])
            self._waiting_vehicle[veh.id] = veh

    def create_waiting_vehicle(self, node: str):
        assert node in self.graph.nodes
        # veh = self.fleet.create_waiting_vehicle(self._prefix(node), None, [])
        new_veh = self.fleet.create_vehicle(activity=VehicleActivityStop(node=node))

        if self._observer is not None:
            new_veh.attach(self._observer)
        self._waiting_vehicle[new_veh.id] = new_veh

    def maintenance(self, dt: Dt):
        pass
        # for veh in list(self.fleet.vehicles.values()):
        #     if veh.is_arrived:
        #         log.info(f'Make vehicle {veh.id} waits at {veh.current_link[1]}')
        #         veh.origin = veh.current_link[1]
        #         veh.is_arrived = False
        #         self.fleet.make_vehicle_wait(veh)

    def rebalancing(self, next_demand: List[User], horizon: Dt):
        pass

    def replaning(self):
        pass

    def matching(self, users: List[Tuple[User, str]]):
        for user in users:
            user.available_mobility_service = frozenset([self.id])

            upos = user.position
            upath = list(user.path.nodes)

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
                        nearest_veh.destination = user.current_node
                        log.info(f"Compute veh path to user {nearest_veh.origin} -> {user.current_node}")
                        available_services = user.available_mobility_service
                        available_services = set() if available_services is None else available_services
                        veh_path = dijkstra(self.graph, nearest_veh.origin, user.current_node, 'travel_time', available_services)
                        if veh_path.path_cost == float('inf'):
                            raise PathNotFound(nearest_veh.origin, user.current_node)
                        veh_path = self._construct_veh_path(list(veh_path.nodes)[:-1]+upath[upath.index(user._current_node):upath.index(drop_node)+1])
                        nearest_veh.set_path(veh_path)
                        nearest_veh.take_next_user(user, drop_node)
                        return

            log.warning(f"No vehicule available for {user}")

    def create_depot(self, id, position, capacity):
        self.depots[id] = {'position': position,
                           'capacity': capacity,
                           'veh': set()}

    # def request_vehicle(self, user: User, drop_node:str) -> None:
    #     user.available_mobility_service = frozenset([self.id])
    #
    #     upos = user.position
    #     upath = list(user.path.nodes)
    #
    #     vehs = list(self.fleet.vehicles.keys())
    #
    #     while vehs:
    #         veh_pos = np.array([self.fleet.vehicles[v].position for v in vehs])
    #         dist_vector = np.linalg.norm(veh_pos - upos, axis=1)
    #         nearest_veh_index = np.argmin(dist_vector)
    #         nearest_veh = vehs[nearest_veh_index]
    #
    #         vehs.remove(nearest_veh)
    #         choosen_veh = self.fleet.vehicles[nearest_veh]
    #         if not choosen_veh.is_full:
    #             if choosen_veh.is_empty:
    #                 nearest_veh.destination = user.current_node
    #                 log.info(f"Compute veh path to user {nearest_veh.origin} -> {user.current_node}")
    #                 available_services = user.available_mobility_service
    #                 available_services = set() if available_services is None else available_services
    #                 veh_path = dijkstra(self.graph, nearest_veh.origin, user.current_node, 'travel_time', available_services)
    #                 if veh_path.path_cost == float('inf'):
    #                     raise PathNotFound(nearest_veh.origin, user.current_node)
    #                 veh_path = self._construct_veh_path(list(veh_path.nodes)[:-1]+upath[upath.index(user._current_node):upath.index(drop_node)+1])
    #                 nearest_veh.set_path(veh_path)
    #                 nearest_veh.take_next_user(user, drop_node)
    #                 return
    #
    #     log.warning(f"No vehicule available for {user}")



        # if self.fleet.nb_waiting_vehicles > 0:
        #     vehicles = list(self.fleet._waiting.values())
        #     veh_pos = np.array([v.position for v in vehicles])
        #     dist_vector = np.linalg.norm(veh_pos-upos, axis=1)
        #
        #     nearest_veh_index = np.argmin(dist_vector)
        #     nearest_veh = vehicles[nearest_veh_index]
        #     nearest_veh.destination = user.current_node
        #     log.info(f"Compute veh path to user {nearest_veh.origin} -> {user.current_node}")
        #     veh_path = bidirectional_dijkstra(self.graph, nearest_veh.origin, user.current_node, 'time', None)
        #     if veh_path.path_cost == float('inf'):
        #         raise PathNotFound(nearest_veh.origin, user.current_node)
        #     log.info(f"{self.id} set VEH path: {veh_path}")
        #     veh_path = self._construct_veh_path(list(veh_path.nodes)[:-1]+upath[upath.index(user._current_node):upath.index(drop_node)+1])
        #     log.info(f"{self.id} set VEH path: {veh_path}")
        #     nearest_veh.set_path(veh_path)
        #     nearest_veh.take_next_user(user, drop_node)
        #
        #     self.fleet.start_waiting_vehicle(nearest_veh.id)

    def __dump__(self):
        return {"TYPE": ".".join([OnDemandCarMobilityService.__module__, OnDemandCarMobilityService.__name__]),
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'])
        return new_obj