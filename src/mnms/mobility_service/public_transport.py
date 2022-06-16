import sys
from collections import defaultdict, deque
from copy import deepcopy
from functools import cached_property
from importlib import import_module
from typing import Type, List

from mnms.log import create_logger
from mnms.mobility_service.abstract import AbstractMobilityService, AbstractMobilityGraphLayer
from mnms.tools.cost import create_service_costs
from mnms.tools.exceptions import VehicleNotFoundError
from mnms.time import TimeTable, Time, Dt
from mnms.vehicles.veh_type import Vehicle, Bus, Metro

log = create_logger(__name__)


class PublicTransportMobilityService(AbstractMobilityService):
    def __init__(self, id:str):
        super(PublicTransportMobilityService, self).__init__(id)
        self._next_veh_departure = dict()
        self.vehicles = defaultdict(deque)

        self._timetable_iter = dict()
        self._current_time_table = dict()
        self._next_time_table = dict()
        self._next_veh_departure = defaultdict(lambda: None)

    @cached_property
    def lines(self):
        return self.layer.lines

    def clean_arrived_vehicles(self, lid:str):
        if len(self.vehicles[lid]) > 0:
            first_veh = self.vehicles[lid][-1]
            if first_veh.is_arrived:
                log.info(f"Deleting arrived veh: {first_veh}")
                self.vehicles[lid].pop()
                self.fleet.delete_vehicle(first_veh.id)
                self.clean_arrived_vehicles(lid)

    def construct_veh_path(self, lid):
        veh_path = list()
        path = self.lines[lid]['nodes']
        for i in range(len(path) - 1):
            unode = path[i]
            dnode = path[i+1]
            key = (unode, dnode)
            veh_path.append((key, self.graph.links[key].costs['length']))
        return veh_path

    def new_departures(self, time, dt, lid:str, all_departures=None):
        veh_path = self.construct_veh_path(lid)

        if all_departures is None:
            if self._next_veh_departure[lid] is None:
                new_veh = self.fleet.create_waiting_vehicle(self.lines[lid]['nodes'][0], self.lines[lid]['nodes'][-1], veh_path)
                self._next_veh_departure[lid] = (self._current_time_table[lid], new_veh)
            all_departures = list()

        if time > self._current_time_table[lid]:
            self._current_time_table[lid] = self._next_time_table[lid]
            try:
                self._next_time_table[lid] = next(self._timetable_iter[lid])
            except StopIteration:
                return all_departures
            self.new_departures(time, dt, lid, all_departures)

        next_time = time.add_time(dt)
        if time <= self._current_time_table[lid] < next_time:
            all_departures.append(self._next_veh_departure[lid][1])
            self.vehicles[lid].appendleft(self._next_veh_departure[lid][1])
            self._current_time_table[lid] = self._next_time_table[lid]
            try:
                self._next_time_table[lid] = next(self._timetable_iter[lid])
                new_veh = self.fleet.create_waiting_vehicle(self.lines[lid]['nodes'][0], self.lines[lid]['nodes'][-1], veh_path)
                self._next_veh_departure[lid] = (self._current_time_table[lid], new_veh)
            except StopIteration:
                return all_departures
            self.new_departures(time, dt, lid, all_departures)
        return all_departures

    def request_vehicle(self, user: "User", drop_node:str) -> None:
        start = user._current_node

        for lid, line in self.lines.items():
            if start in line['nodes']:
                user_line = line
                user_line_id = lid
                break
        else:
            log.error(f'{user} start is not in the PublicTransport mobility service {self.id}')
            sys.exit(-1)

        if self.graph.nodes[start].radj:
            departure_time, waiting_veh = self._next_veh_departure[user_line_id]
            waiting_veh.take_next_user(user, drop_node)
            return
        else:
            curr_veh = None
            next_veh = None
            it_veh = iter(self.vehicles[user_line])
            ind_start = user_line.stops.index(start)
            try:
                curr_veh = next(it_veh)
                next_veh = next(it_veh)
            except StopIteration:
                if curr_veh is not None:
                    curr_veh.take_next_user(user, drop_node)
                    return
                else:
                    raise VehicleNotFoundError(user, self)

            while True:
                ind_curr_veh = user_line.stops.index(curr_veh.current_link[1])
                ind_next_veh = user_line.stops.index(next_veh.current_link[1])
                if ind_curr_veh <= ind_start < ind_next_veh:
                    curr_veh.take_next_user(user, drop_node)
                    return
                try:
                    curr_veh = next_veh
                    next_veh = next(it_veh)
                except StopIteration:
                    ind_curr_veh = user_line.stops.index(curr_veh.current_link[1])
                    if ind_curr_veh <= ind_start:
                        curr_veh.take_next_user(user, drop_node)
                        return
                    else:
                        log.info(f"{user}, {user._current_node}")
                        log.info(f"{curr_veh.current_link}")
                        raise VehicleNotFoundError(user, self)

    def update(self, dt: Dt):
        for lid in self.lines:
            for new_veh in self.new_departures(self._tcurrent, dt, lid):
                self.fleet.start_waiting_vehicle(new_veh.id)
                if self._observer is not None:
                    new_veh.attach(self._observer)

            self.clean_arrived_vehicles(lid)

    def service_level_costs(self, nodes:List[str]) -> dict:
        """
        Must return a dict of costs representing the cost of the service computed from a path
        Parameters
        ----------
        path

        Returns
        -------

        """
        return create_service_costs()

    def __dump__(self):
        return {"TYPE": ".".join([PublicTransportMobilityService.__module__, PublicTransportMobilityService.__name__]),
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'])
        return new_obj


class PublicTransportGraphLayer(AbstractMobilityGraphLayer):
    """Public transport class, manage its lines

    Parameters
    ----------
    id: str
        Id of the public transport class
    default_speed: float
        Default speed of the public transport

    """
    def __init__(self, id:str, veh_type:Type[Vehicle], default_speed:float, services:List[PublicTransportMobilityService]=None, observer=None):
        assert issubclass(veh_type, Vehicle)
        super(PublicTransportGraphLayer, self).__init__(id, veh_type, default_speed, services, observer)
        self.lines = dict()
        self.line_connections = []

    def add_mobility_service(self, service:"AbstractMobilityService"):
        assert isinstance(service, PublicTransportMobilityService), f"PublicTransportGraphLayer only accept mobility services with type PublicTransportMobilityService"
        super(PublicTransportGraphLayer, self).add_mobility_service(service)

    def show_lines(self) -> None:
        print(self.lines)

    def connect_lines(self, ulineid: str, dlineid: str, unid: str, dnid:str, costs:dict=None, two_ways=True) -> None:
        assert unid in self.lines[ulineid].stops
        assert dnid in self.lines[dlineid].stops
        c = {'waiting_time': self.lines[dlineid]._timetable.get_freq() / 2, "length": 0}
        if costs is not None:
            c.update(costs)

        self.graph.create_link('_'.join([unid, dnid]),
                               unid,
                               dnid,
                               c,
                               [None],
                               self.id)

        self.line_connections.append('_'.join([unid, dnid]))

        if two_ways:
            c = {'waiting_time': self.lines[ulineid]._timetable.get_freq() / 2, "length": 0}
            if costs is not None:
                c.update(costs)
            self.graph.create_link('_'.join([dnid, unid]),
                                   dnid,
                                   unid,
                                   c,
                                   [None],
                                   self.id)

            self.line_connections.append('_'.join([dnid, unid]))

    def connect_to_service(self, nid) -> dict:
        for line in self.lines.values():
            if nid in line.stops:
                return {"time": line.timetable.get_freq()/2}

    def __dump__(self) -> dict:
        return {"TYPE": ".".join([PublicTransportGraphLayer.__module__, PublicTransportGraphLayer.__name__]),
                "ID": self.id,
                "VEH_TYPE":  ".".join([self._veh_type.__module__, self._veh_type.__name__]),
                "DEFAULT_SPEED": self.default_speed,
                "LINES": [l.__dump__() for l in self.lines.values()],
                "CONNECTIONS": [self.graph.get_link(l).__dump__() for l in self.line_connections],
                "SERVICES": [s.__dump__() for s in self.mobility_services.values()]}

    @classmethod
    def __load__(cls, data: dict) -> "PublicTransport":
        veh_class_name = data['VEH_TYPE'].split('.')[-1]
        veh_module_name = data['VEH_TYPE'].removesuffix('.'+veh_class_name)
        veh_module = import_module(veh_module_name)
        veh_class = getattr(veh_module, veh_class_name)

        new_obj = cls(data['ID'], veh_class, data["DEFAULT_SPEED"])
        for ldata in data['LINES']:
            tt = []
            for time in ldata['TIMETABLE']:
                new_time = Time(time)
                tt.append(new_time)
            new_line = new_obj.add_line(ldata['ID'], TimeTable(tt))
            [new_line.add_stop(s['ID'], s['REF_NODE']) for s in ldata['STOPS']]
            [new_line.connect_stops(l['ID'],
                                    l['UPSTREAM'],
                                    l['DOWNSTREAM'],
                                    l['COSTS']['length'],
                                    l['REF_LINKS'],
                                    l['COSTS']) for l in ldata['LINKS']]
        return new_obj

    def construct_veh_path(self, lid: str):
        veh_path = list()
        path = self.lines[lid].stops
        for i in range(len(path) - 1):
            unode = path[i]
            dnode = path[i+1]
            if self._graph.nodes[dnode].layer == self.id:
                key = (unode, dnode)
                veh_path.append((key, self._graph.sections[key].costs['length']))
            else:
                break
        return veh_path

    def connect_to_layer(self, nid) -> dict:
        for line in self.lines.values():
            if nid in line.stops:
                return {"wating_time": line._timetable.get_freq() / 2}


