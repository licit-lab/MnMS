import sys
from collections import defaultdict, deque
from copy import deepcopy
from functools import cached_property
from importlib import import_module
from typing import Type, List

from mnms.log import create_logger
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.graph.abstract import AbstractLayer
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
            link = self.graph.nodes[unode].adj[dnode]
            veh_path.append((key, link.length))
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
            it_veh = iter(self.vehicles[user_line_id])
            ind_start = user_line["nodes"].index(start)
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
