from abc import ABC, abstractmethod, ABCMeta
from typing import List, Tuple, Optional, Dict
from mnms.time import Time, Dt
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.log import create_logger
from mnms.vehicles.veh_type import Vehicle, VehicleActivity
from mnms.demand.user import User
from mnms.tools.observer import TimeDependentSubject
from mnms.tools.cost import create_service_costs
from mnms.vehicles.veh_type import VehicleState, VehicleActivityStop, VehicleActivityPickup, VehicleActivityServing

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


class OnVehicleSharingMobilityService(AbstractMobilityService):

    def __init__(self,
                 _id: str,
                 dt_matching: int,
                 dt_step_maintenance: int = 0):
        super(OnVehicleSharingMobilityService, self).__init__(_id, 1, dt_matching, dt_step_maintenance)

        self.stations = dict()
        self.map_node_station = dict()

    def create_station(self, id_station: str, node: str, capacity: int, nb_initial_veh: int = 0, free_floating=False) \
            -> Station:

        # assert node in self.graph.nodes

        station = Station(id_station, node, capacity, free_floating)

        for v in range(nb_initial_veh):
            v = self.fleet.create_vehicle(node,
                                          capacity=self._veh_capacity,
                                          activities=[VehicleActivityStop(node=node)])
            v.set_position(self.graph.nodes[node].position)
            station.waiting_vehicles.append(v)

            if self._observer is not None:
                v.attach(self._observer)

        self.stations[id_station] = station

        self.layer.stations.append({'id': id_station, 'node': node, 'position': self.layer.roads.nodes[node].position})

        # TO DO: 2 stations may be on the same node (free-floating stations)
        self.map_node_station[node] = id_station

        return station

    def remove_station(self, id_station: str):

        self.stations = [x for x in self.stations if not (id_station == x.get('id'))]
        self.map_node_station.pop(self.stations[id_station].node)

        # TODO : remove transit links

    def init_free_floating_vehicles(self, id_node: str, nb_veh: int):
        """
        Create the vehicles and the corresponding free-floating station

        Parameters
        ----------
        id_node: Node where the vehicles are
        nb_veh: Number of shared vehicles to be created at this node

        """
        id_station = 'ff_station_' + self.id + '_' + id_node
        self.create_station(id_station, id_node, nb_veh, nb_veh, True)

    def create_free_floating_station(self, veh: Vehicle):
        """
        Create the free floating station corresponding to the vehicle

        Parameters
        ----------
        veh: Vehicle

        Returns
        -------

        """
        assert (veh.state == 'STOP')

        id_station = 'ff_station_' + self.id + '_' + veh.current_node

        if id_station in self.stations.keys:
            self.stations[id_station].waiting_vehicles.append(veh)
        else:
            station = self.create_station(id_station, veh.current_node, 1, 0, True)
            station.waiting_vehicles.append(veh)

    def available_vehicles(self, id_station: str):

        assert id_station in self.stations

        node = self.stations[id_station].node

        return [v.id for v in self.fleet.vehicles.values() if (node == v.current_node and v.state == VehicleState.STOP)]

    def step_maintenance(self, dt: Dt):

        # TO DO: optimisation (not manage all the vehicle)
        for veh in self.fleet.vehicles.values():
            if veh.state is VehicleState.STOP:
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

        station = self.map_node_station[user.current_node]
        vehs = self.available_vehicles(station)

        if len(vehs) > 0:
            choosen_veh = vehs[0]
            self._cache_request_vehicles[uid] = choosen_veh, ''
            service_dt = Dt()
        else:
            service_dt = Dt(hours=24)

        return service_dt

    def matching(self, user: User, drop_node: str):

        veh, veh_path = self._cache_request_vehicles[user.id]
        upath = list(user.path.nodes)
        upath = upath[upath.index(user._current_node):upath.index(drop_node) + 1]
        user_path = self.construct_veh_path(upath)
        veh_path = user_path

        activities = [
            VehicleActivityServing(node=drop_node,
                                   path=user_path,
                                   user=user)
        ]

        self.fleet.vehicles[veh].add_activities(activities)
        self.fleet.vehicles[veh].next_activity()
        user.set_state_inside_vehicle()

        station = self.stations[self.map_node_station[user._current_node]]
        # Delete the vehicle from the waiting vehicle list
        station.waiting_vehicles.remove(veh)

        # Delete the station if it is free-floating and empty
        if station.free_floating and len(station.waiting_vehicles) == 0:
            self.remove_station(station.id)

    def replanning(self, veh: Vehicle, new_activities: List[VehicleActivity]) -> List[VehicleActivity]:
        pass

    def rebalancing(self, next_demand: List[User], horizon: Dt):
        pass

    def service_level_costs(self, nodes: List[str]) -> dict:
        return create_service_costs()

    def __dump__(self):
        return {
            "TYPE": ".".join([OnVehicleSharingMobilityService.__module__, OnVehicleSharingMobilityService.__name__]),
            "DT_MATCHING": self._dt_matching,
            "VEH_CAPACITY": self._veh_capacity,
            "ID": self.id,
            'STATIONS': [{'ID': s._id, 'NODE': s.node, 'CAPACITY': s.capacity} for s in self.stations.values()]
            }

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'], data["DT_MATCHING"], data["VEH_CAPACITY"])

        # TODO: stations loading (complex...)

        return new_obj
