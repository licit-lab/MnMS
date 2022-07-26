from random import sample

import numpy as np

from mnms import create_logger
from mnms.demand import User
from mnms.graph.shortest_path import bidirectional_dijkstra
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.time import Dt
from mnms.tools.exceptions import PathNotFound

log = create_logger(__name__)


class PersonalCarMobilityService(AbstractMobilityService):
    def __init__(self, id:str='PersonalCar'):
        super(PersonalCarMobilityService, self).__init__(id)

    def request_vehicle(self, user: "User", drop_node:str) -> None:
        upath = list(user.path.nodes)
        upath = upath[upath.index(user._current_node):upath.index(drop_node)+1]
        veh_path = self._construct_veh_path(upath)
        new_veh = self.fleet.create_vehicle(upath[0], upath[-1], veh_path, capacity=1)
        new_veh.take_next_user(user, drop_node)
        new_veh.start_user_trip(user.id, user.path.nodes[0])
        if self._observer is not None:
            new_veh.attach(self._observer)

    def update(self, dt:Dt):
        for veh in list(self.fleet.vehicles.values()):
            if veh.is_arrived:
                self.fleet.delete_vehicle(veh.id)

    def __dump__(self):
        return {"TYPE": ".".join([PersonalCarMobilityService.__module__, PersonalCarMobilityService.__name__]),
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'])
        return new_obj


class OnDemandCarMobilityService(AbstractMobilityService):
    def __init__(self, id:str):
        super(OnDemandCarMobilityService, self).__init__(id)
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
        veh = self.fleet.create_waiting_vehicle(self._prefix(node), None, [])
        if self._observer is not None:
            veh.attach(self._observer)
        self._waiting_vehicle[veh.id] = veh

    def update(self, dt:Dt):
        for veh in list(self.fleet.vehicles.values()):
            if veh.is_arrived:
                log.info(f'Make vehicle {veh.id} waits at {veh.current_link[1]}')
                veh.origin = veh.current_link[1]
                veh.is_arrived = False
                self.fleet.make_vehicle_wait(veh)

    def create_depot(self, id, position, capacity):
        self.depots[id] = {'postion': position,
                           'capacity': capacity,
                           'veh': set()}

    def request_vehicle(self, user: User, drop_node:str) -> None:
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
                    veh_path = bidirectional_dijkstra(self.graph, nearest_veh.origin, user.current_node, 'time', None)
                    if veh_path.path_cost == float('inf'):
                        raise PathNotFound(nearest_veh.origin, user.current_node)
                    veh_path = self._construct_veh_path(list(veh_path.nodes)[:-1]+upath[upath.index(user._current_node):upath.index(drop_node)+1])
                    nearest_veh.set_path(veh_path)
                    nearest_veh.take_next_user(user, drop_node)
                    return

        log.warning(f"No vehicule available for {user}")



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