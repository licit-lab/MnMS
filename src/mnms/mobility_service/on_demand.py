from typing import Tuple, Dict, List

import numpy as np

from hipop.shortest_path import dijkstra

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
                 matching_strategy: str='nearest_idle_vehicle'):
        super(OnDemandMobilityService, self).__init__(id,  veh_capacity=1, dt_matching=dt_matching,
            dt_periodic_maintenance=dt_periodic_maintenance)

        self.gnodes = dict()
        self._matching_strategy = matching_strategy

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

    def request(self, user: User, drop_node: str) -> Dt:
        """Method that associates a vehicle of this mobility service to the requesting
        user. It calls the proper matching strategy.

        Args:
            -user: user requesting a ride
            -drop_node: node where user would like to be dropped off

        Returns:
            -service_dt: waiting time before pick-up
        """
        if self._matching_strategy == 'nearest_idle_vehicle':
            service_dt = self.request_nearest_idle_vehicle(user, drop_node)
        elif self._matching_strategy == 'nearest_vehicle_in_radius':
            service_dt = self.request_nearest_vehicle_in_radius(user, drop_node)
        else:
            log.error(f'Unknown matching strategy {self._matching_strategy} for {self.id} mobility service')
            sys.exit(-1)
        return service_dt


    def request_nearest_vehicle_in_radius(self, user: User, drop_node: str, radius: float = 5000) -> Dt:
        """Assigns the vehicle with the smallest pick up time among vehicles located within
        a certain radius around the user pick-up node. Vehicles are considered even if they
        already have activities in their plan (the activities related to the new user are considered
        inserted at the end of the vehicle plan).

        Args:
            -user: user requesting a ride
            -drop_node: node where user would like to be dropped off
            -radius: radius wihtin which vehicles are considered for the match

        Returns:
            -service_dt: waiting time before pick-up

        """
        upos = user.position
        uid = user.id
        vehs = np.array(list(self.fleet.vehicles.values()))
        if len(vehs) == 0:
            return Dt(hours=24)
        vehs_pos = np.array([v.position for v in vehs])

        # Search for the vehicles close to the user
        dist_vector = np.linalg.norm(vehs_pos - upos, axis=1)
        nearest_vehs_indices = dist_vector <= radius # radius in meters
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
            self._cache_request_vehicles[uid] = candidates[0][0], candidates[0][2]
        else:
            return Dt(hours=24)

        return candidates[0][1]

    def request_nearest_idle_vehicle(self, user: User, drop_node: str) -> Dt:
        """Assigns the nearest idle vehicle to the requesting user.

        Args:
            -user: User requesting a ride
            -drop_node: node where user would like to be dropped off

        Returns:
            -service_dt: waiting time before pick-up
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
                available = True if ((choosen_veh.activity_type in [ActivityType.STOP, ActivityType.REPOSITIONING]) and (not choosen_veh.activities)) else False
                if available:
                    # Compute pick-up path and cost from end of current activity
                    veh_last_node = choosen_veh.activity.node if not choosen_veh.activities else \
                    choosen_veh.activities[-1].node
                    veh_path, cost = dijkstra(self.graph, veh_last_node, user.current_node, 'travel_time', {self.layer.id: self.id}, {self.layer.id})
                    # If vehicle cannot reach user, skip and consider next vehicle
                    if cost == float('inf'):
                        continue
                        # raise PathNotFound(choosen_veh._current_node, user.current_node)

                    service_dt = Dt(seconds=cost)
                    self._cache_request_vehicles[uid] = choosen_veh, veh_path
                    break

        return service_dt

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
                 matching_strategy: str = 'nearest_idle_vehicle'):
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
