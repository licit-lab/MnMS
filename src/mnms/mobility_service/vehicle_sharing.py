from abc import ABC, abstractmethod, ABCMeta
from typing import List, Tuple, Optional, Dict
from mnms.time import Time, Dt
from mnms.mobility_service.abstract import AbstractMobilityService, Request
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

    def __repr__(self):
        return f'Station({self._id}, {len(self.waiting_vehicles)}/{self.capacity})'


class VehicleSharingMobilityService(AbstractMobilityService):

    def __init__(self,
                 id: str,
                 free_floating_possible: bool,
                 dt_matching: int,
                 dt_periodic_maintenance: int = 0,
                 critical_nb_vehs: int = 10,
                 alpha: float = 600,
                 beta : float = 0.1):
        """Constructor of VehicleSharingMobilityService objects.

        Args:
            -id: the id of the mobility service
            -free_floating_possible:
            -dt_matching: the number of flow time steps elapsed between two calls
             of the matching
            -dt_periodic_maintenance: the number of flow steps elapsed between two
             call of the periodic maintenance
            -critical_nb_vehs: the number of vehicles available at station below which
             the estimated waiting time starts to increase
            -alpha: maximum estimated pickup time
            -beta: parameter controlling the shape of the estimated pickup time
             curve
        """
        super(VehicleSharingMobilityService, self).__init__(id, veh_capacity=1, dt_matching=dt_matching,
            dt_periodic_maintenance=dt_periodic_maintenance)

        self.free_floating_possible = free_floating_possible
        self.critical_nb_vehs = critical_nb_vehs
        self.alpha = alpha
        self.beta = beta
        self.stations = dict()
        self.map_node_station = dict()

    def create_station(self, id_station: str, dbroads_node: str, layer_node:str='', capacity: int=30, nb_initial_veh: int = 0, free_floating=False) \
            -> Station:
        """Method that creates a station for the shared vehicles of this service.

        Args:
            -id_station: id of the station to create
            -dbroads_node: id of the roads node where the station should be created
            -layer_node: id of the multilayer graph node where the station should be created
            -capacity: number of parking spots in the station
            - nb_initial_veh: number of vehicles to create jointly with the station
            -free_floating: boolean which is True is the station is free-floating, False
             otherwise

        Returns:
            -station: the created station
        """
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
            -new_users: users who are about to depart but not yet taken into account
             by the user_low
            -user_flow: the UserFlow object of the simulation
            -decision_model: the AbstractDecisionModel object of the simulation

        Returns:
            -users_canceling: the list of users who should cancel because the station was
             removed
        """
        log.info(f'{self._id} vehicle sharing service: Station {id_station} is diconnected and removed')
        self.map_node_station.pop(self.stations[id_station].node)
        del (self.stations[id_station])

        deleted_links = self.layer.disconnect_station(id_station)

        # Manage users who were supposed to use one of the deleted links
        users_canceling = user_flow.manage_links_removal_after_match(deleted_links, new_users, matched_user_id, self, decision_model)

        return users_canceling


    def init_free_floating_vehicles(self, id_node: str, nb_veh: int):
        """
        Creates the vehicles and the corresponding free-floating station.

        Args:
            -id_node: Roads node where the vehicles are
            -nb_veh: Number of shared vehicles to be created at this node
        """
        id_station = 'ff_station_' + self.id + '_' + id_node
        self.create_station(id_station, id_node, '', nb_veh, nb_veh, True)

    def create_free_floating_station(self, veh: Vehicle):
        """
        Creates the free floating station corresponding to the vehicle

        Args:
            -veh: Vehicle
        """
        id_station = 'ff_station_' + self.id + '_' + veh.current_node

        if id_station in self.stations.keys():
            self.stations[id_station].waiting_vehicles.append(veh)
        else:
            station = self.create_station(id_station, '', veh.current_node, 1, 0, True)
            station.waiting_vehicles.append(veh)
            self.layer.connect_station(id_station, self.layer._multi_graph.odlayer, 500)

    def available_vehicles(self, id_station: str):
        """Method that finds the vehicles available currently at a given station.

        Args:
            -id_station: id of the station where to find for available vehicles

        Returns:
            -vehs: the list of available vehicles ids
        """
        assert id_station in self.stations

        node = self.stations[id_station].node

        vehs = [v.id for v in self.fleet.vehicles.values() if (node == v.current_node and v.activity_type==ActivityType.STOP)]

        return vehs

    def step_maintenance(self, dt: Dt):
        """Method that proceeds to the maintenance phase of this service.
        It associates the stopped vehicles to the existing stations and eventually
        create a new free-floating station when the service authorizes it.

        Args:
            -dt: time elapsed since the previous maintenance phase
        """
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

    def estimate_pickup_time_for_planning(self, pu_node):
        """Method that returns the estimated pickup time at a specific node. This
        information is used by user to (re)plan.

        Args:
            -pu_node: pickup node

        Returns:
            -estimated pickup time in seconds
        """
        if self.free_floating_possible:
            # Null estimated pickup time for free floating vehicle sharing
            return 0
        else:
            # Find back the station at pickup node
            if pu_node in self.map_node_station.keys():
                station_id = self.map_node_station[pu_node]
                station = self.stations[station_id]
                estimated_putime = self.alpha * (1 - (len(station.waiting_vehicles)/self.critical_nb_vehs)**self.beta)
                return estimated_putime
            else:
                log.error(f'Cannot find a {self.id} station at pickup node {pu_node}...')
                sys.exit(-1)

    def request(self, user: User, drop_node: str) -> Dt:
        """Method that associates a requesting user to a vehicle of the service.

            Args:
                -user: User requesting a vehicle
                -drop_node: The station of vehicle sharing

            Returns:
                -service_dt: estimated pickup time which is null if a vehicle is
                 available, inf otherwise
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

    def matching(self, request: Request, new_users: List[User], user_flow: UserFlow, decision_model: AbstractDecisionModel, dt: Dt):
        """Method that proceeds to the matching between a requesting user and an identified vehicle.

        Args:
            -request: the request to match
            -new_users: the list of users who have just/are about to depart but not
             yet considered in the user flow
            -user_flow: the simulation user flow module
            -decision_model: the simulation decision model
            -dt: the flow time step

        Returns:
            -users_canceling: the list of users who should cancel their request for
             this service because a station has been removed
        """
        user = request.user
        drop_node = request.drop_node
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
        immediate_match = self._tcurrent - request.request_time <= dt
        act_start_time = request.request_time if immediate_match else self._tcurrent
        veh.next_activity(act_start_time)
        user.set_state_inside_vehicle()
        # Take into account effective remaining duration to move during the current flow step
        # if match has been immediate
        if immediate_match:
            veh.dt_move = self._tcurrent - request.request_time

        station = self.stations[self.map_node_station[user.current_node]]
        # Delete the vehicle from the waiting vehicle list
        station.waiting_vehicles.remove(veh)

        # Delete the station if it is free-floating and empty
        if station.free_floating and len(station.waiting_vehicles) == 0:
            users_canceling = self.remove_station(station._id, user.id, new_users, user_flow, decision_model)
            return users_canceling

        users_canceling = []
        return users_canceling

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
