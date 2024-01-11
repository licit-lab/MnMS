from abc import ABC, abstractmethod, ABCMeta
from typing import List, Tuple, Optional, Dict
from mnms.time import Time, Dt
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.log import create_logger
from mnms.vehicles.veh_type import Vehicle, VehicleActivity
from mnms.demand.user import User, UserState
from mnms.tools.observer import TimeDependentSubject
from mnms.tools.cost import create_service_costs
from mnms.vehicles.veh_type import VehicleActivityStop, VehicleActivityPickup, VehicleActivityServing, ActivityType
from mnms.travel_decision.abstract import Event, AbstractDecisionModel
from mnms.flow.user_flow import UserFlow

log = create_logger(__name__)


class Station(TimeDependentSubject):

    def __init__(self,
                 _id: str,
                 node: str,
                 capacity: int,
                 free_floating: bool = False):
        self._id = _id
        self.node = node
        self.capacity = capacity
        self.free_floating = free_floating

        self.waiting_vehicles = []


class VehicleSharingMobilityService(AbstractMobilityService):

    def __init__(self,
                 _id: str,
                 free_floating_possible: bool,
                 dt_matching: int,
                 dt_step_maintenance: int = 0):
        super(VehicleSharingMobilityService, self).__init__(_id, 1, dt_matching, dt_step_maintenance)

        self.free_floating_possible = free_floating_possible
        self.stations = dict()
        self.map_node_station = dict()

    def create_station(self, id_station: str, dbroads_node: str, layer_node:str='', capacity: int=30, nb_initial_veh: int = 0, free_floating=False) \
            -> Station:

        if len(dbroads_node)>0:
            layer_node = self.layer.id + '_' + dbroads_node
        else:
            roaddb_node = self.layer.map_reference_nodes[layer_node]


        assert layer_node in self.graph.nodes

        station = Station(id_station, layer_node, capacity, free_floating)

        for v in range(nb_initial_veh):
            v = self.fleet.create_vehicle(layer_node,
                                          capacity=self._veh_capacity,
                                          activities=[VehicleActivityStop(node=layer_node)])
            v.set_position(self.graph.nodes[layer_node].position)
            station.waiting_vehicles.append(v)

            if self._observer is not None:
                v.attach(self._observer)

        self.stations[id_station] = station

        roaddb_node = self.layer.map_reference_nodes[layer_node]
        self.layer.stations.append({'id': id_station, 'node': layer_node, 'position': self.layer.roads.nodes[roaddb_node].position})

        # TO DO: 2 stations may be on the same node (free-floating stations)
        self.map_node_station[layer_node] = id_station

        return station

    def remove_station(self, id_station: str, matched_user_id: str, new_users: List[User], user_flow: UserFlow, decision_model: AbstractDecisionModel):
        """Method that disconnects and deletes a (free-floating) station from the
        rest of the multi layer graph.

        Args:
            -id_station: id of the station to remove
            -matched_user_id: user who have just been matched
            -user_flow: the UserFlow object of the simulation
            -decision_model: the AbstractDecisionModel object of the simulation
        """
        log.info(f'{self._id} vehicle sharing service: Station {id_station} is diconnected and removed')
        self.map_node_station.pop(self.stations[id_station].node)
        del (self.stations[id_station])

        deleted_links = self.layer.disconnect_station(id_station)

        # Gathers users who were supposed to use one of the deleted links
        interrupted_users = []
        users_canceling = []
        for u in list(user_flow.users.values()) + new_users:
            if u.id != matched_user_id and u.path is not None:
                unodes = u.path.nodes
                path_links = [(unodes[i],unodes[i+1]) for i in range(len(unodes)-1)]
                intersect = set(deleted_links).intersection(set(path_links))
                if len(intersect) > 0:
                    log.info(f"User {u.id} was supposed to pass through links {intersect} which were deleted, trigger an INTERRUPTION event (current node = {u.current_node}, state = {u.state})")
                    interrupted_users.append(u)
                    # Clean eventual request already formulated by user to this service
                    if u.id in self._user_buffer.keys():
                        if u.state == UserState.WAITING_ANSWER:
                            # This user is waiting to be matched with a vehicle of the station we have just removed,
                            # turn her to STOP state, and save the fact that she should cancel her request
                            u.set_state_stop()
                        users_canceling.append(u.id)
        if interrupted_users:
            decision_model.add_users_for_planning(interrupted_users, [Event.INTERRUPTION]*len(interrupted_users))
            # NB: the planning will be called before the next user flow step so no need to interrupt user path now
        return users_canceling


    def init_free_floating_vehicles(self, id_node: str, nb_veh: int):
        """
        Create the vehicles and the corresponding free-floating station

        Parameters
        ----------
        id_node: Node where the vehicles are
        nb_veh: Number of shared vehicles to be created at this node

        """
        id_station = 'ff_station_' + self.id + '_' + id_node
        self.create_station(id_station, id_node, '', nb_veh, nb_veh, True)

    def create_free_floating_station(self, veh: Vehicle):
        """
        Create the free floating station corresponding to the vehicle

        Parameters
        ----------
        veh: Vehicle

        Returns
        -------

        """
        id_station = 'ff_station_' + self.id + '_' + veh.current_node

        if id_station in self.stations.keys():
            self.stations[id_station].waiting_vehicles.append(veh)
        else:
            station = self.create_station(id_station, '', veh.current_node, 1, 0, True)
            station.waiting_vehicles.append(veh)
            self.layer.connect_station(id_station, self.layer._multi_graph.odlayer, 500)

    def available_vehicles(self, id_station: str):

        assert id_station in self.stations

        node = self.stations[id_station].node

        return [v.id for v in self.fleet.vehicles.values() if (node == v.current_node and v.activity_type==ActivityType.STOP)]

    def step_maintenance(self, dt: Dt):

        # TO DO: optimisation (not manage all the vehicle)
        for veh in self.fleet.vehicles.values():
            if veh.activity_type is ActivityType.STOP:
                _current_node = veh.current_node

                if self.map_node_station.get(_current_node):
                    station_id = self.map_node_station[_current_node]

                    if veh not in self.stations[station_id].waiting_vehicles:
                        self.stations[station_id].waiting_vehicles.append(veh)
                else:
                    if self.free_floating_possible:
                        self.create_free_floating_station(veh)

    def periodic_maintenance(self, dt: Dt):
        pass

    def request(self, user: User, drop_node: str) -> Dt:
        """

                Args:
                    user: User requesting a vehicle
                    drop_node: The station of vehicle sharing

                Returns: 0 if a vehicle is available, inf if not

                """
        uid = user.id

        if user.current_node in self.map_node_station:
            station = self.map_node_station[user.current_node]
        else:
            return Dt(hours=24)

        vehs = self.available_vehicles(station)

        if len(vehs) > 0:
            choosen_veh = vehs[0]
            self._cache_request_vehicles[uid] = choosen_veh, ''
            service_dt = Dt()
        else:
            service_dt = Dt(hours=24)

        return service_dt

    def matching(self, user: User, drop_node: str, new_users: List[User], user_flow: UserFlow, decision_model: AbstractDecisionModel):
        veh_id, veh_path = self._cache_request_vehicles[user.id]
        log.info(f'User {user.id} matched with vehicle {veh_id} of mobility service {self._id}')
        upath = list(user.path.nodes)
        upath = upath[user.get_current_node_index():user.get_node_index_in_path(drop_node) + 1]
        user_path = self.construct_veh_path(upath)
        veh_path = user_path

        activities = [
            VehicleActivityServing(node=drop_node,
                                   path=user_path,
                                   user=user)
        ]

        veh=self.fleet.vehicles[veh_id]
        veh.add_activities(activities)
        veh.next_activity()
        user.set_state_inside_vehicle()

        station = self.stations[self.map_node_station[user._current_node]]
        # Delete the vehicle from the waiting vehicle list
        station.waiting_vehicles.remove(veh)

        # Delete the station if it is free-floating and empty
        if station.free_floating and len(station.waiting_vehicles) == 0:
            users_canceling = self.remove_station(station._id, user.id, new_users, user_flow, decision_model)
            return users_canceling

        return []

    def replanning(self, veh: Vehicle, new_activities: List[VehicleActivity]) -> List[VehicleActivity]:
        pass

    def rebalancing(self, next_demand: List[User], horizon: Dt):
        pass

    def service_level_costs(self, nodes: List[str]) -> dict:
        return create_service_costs()

    def __dump__(self):
        return {
            "TYPE": ".".join([VehicleSharingMobilityService.__module__, VehicleSharingMobilityService.__name__]),
            "DT_MATCHING": self._dt_matching,
            "VEH_CAPACITY": self._veh_capacity,
            "ID": self.id,
            'STATIONS': [{'ID': s._id, 'NODE': s.node, 'CAPACITY': s.capacity} for s in self.stations.values()]
            }

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data["DT_MATCHING"], data["VEH_CAPACITY"],data['STATIONS'])

        # TODO: stations loading (complex...)

        return new_obj
