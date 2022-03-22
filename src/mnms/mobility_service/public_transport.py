import sys
from collections import defaultdict, deque
from copy import deepcopy
from typing import Type, Tuple, List

from mnms.log import create_logger
from mnms.mobility_service.abstract import AbstractMobilityService, AbstractMobilityGraphLayer
from mnms.tools.containers import CostDict
from mnms.tools.exceptions import VehicleNotFoundError
from mnms.tools.time import TimeTable, Time, Dt
from mnms.vehicles.veh_type import Vehicle, Bus, Metro

log = create_logger(__name__)


def _NoneDefault():
    return None


# TODO: When a Line is created ensure that nodes are ordered
class Line(object):
    """Represent a line of a PublicTransport mobility service

    Parameters
    ----------
    id: str
        Id of the line
    mobility_service: PublicTransport
        The PublicTransport class in which the line is
    timetable: TimeTable
        The time table of departure

    """
    def __init__(self, id: str, graph_layer: "PublicTransportGraphLayer", timetable: "TimeTable"):
        self.id = id
        self.stops = list()
        self.links = set()
        self.graph_layer = graph_layer
        self.service_id = graph_layer.id

        self._service_graph = self.graph_layer.graph
        self._adjacency = defaultdict(_NoneDefault)
        self._rev_adjacency = defaultdict(_NoneDefault)

        self._timetable = timetable

    def add_stop(self, sid:str, ref_node:str=None) -> None:
        self._service_graph.add_node(self._prefix(sid), self.graph_layer.id, ref_node)
        self.stops.append(self._prefix(sid))

    def connect_stops(self, lid:str, up_sid: str, down_sid: str, length:float, costs=None, reference_links=None,
                      reference_lane_ids=None) -> None:
        assert self._prefix(up_sid) in self.stops
        assert self._prefix(down_sid) in self.stops
        costs = {} if costs is None else costs
        costs.update({'length': length})
        self._service_graph.add_link(self._prefix(lid),
                                     self._prefix(up_sid),
                                     self._prefix(down_sid),
                                     costs=costs,
                                     reference_links=reference_links,
                                     reference_lane_ids=reference_lane_ids,
                                     mobility_service=self.graph_layer.id)
        self.links.add(lid)

        p_up_dis = self._prefix(up_sid)
        p_down_dis = self._prefix(down_sid)
        self._adjacency[p_up_dis] = p_down_dis
        self._rev_adjacency[p_down_dis] = p_up_dis


    @property
    def start(self):
        return self.stops[0]

    @property
    def end(self):
        return self.stops[-1]

    def _prefix(self, name):
        return self.id+'_'+name

    def __dump__(self) -> dict:
        stops = deepcopy(self.stops)
        return {"ID": self.id,
                "TIMETABLE": [time.time for time in self.timetable.table],
                "STOPS": [self._service_graph.nodes[s].__dump__() for s in stops],
                "LINKS":[self._service_graph.links[self._service_graph._map_lid_nodes[self._prefix(l)]].__dump__() for l in self.links]}

    def construct_veh_path(self):
        veh_path = list()
        path = self.stops
        for i in range(len(path) - 1):
            unode = path[i]
            dnode = path[i+1]
            key = (unode, dnode)
            veh_path.append((key, self.graph_layer.graph.links[key].costs['length']))
        return veh_path


class PublicTransportMobilityService(AbstractMobilityService):
    def __init__(self, id:str):
        super(PublicTransportMobilityService, self).__init__(id)
        self._next_veh_departure = dict()
        self.vehicles = defaultdict(deque)
        # self._timetable_iter = iter(self.timetable.table)
        # self._current_time_table = next(self._timetable_iter)
        # self._next_time_table = next(self._timetable_iter)
        self._timetable_iter = dict()
        self._current_time_table = dict()
        self._next_time_table = dict()
        self._next_veh_departure = defaultdict(_NoneDefault)

    @property
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

    def new_departures(self, time, dt, line:Line, all_departures=None):
        # log.info(f"{time}, {dt}, {self._current_time_table}")
        veh_path = line.construct_veh_path()

        if all_departures is None:
            if self._next_veh_departure[line.id] is None:
                new_veh = self.fleet.create_waiting_vehicle(line.stops[0], line.stops[-1], veh_path)
                self._next_veh_departure[line.id] = (self._current_time_table[line.id], new_veh)
            all_departures = list()

        if time > self._current_time_table[line.id]:
            self._current_time_table[line.id] = self._next_time_table[line.id]
            try:
                self._next_time_table[line.id] = next(self._timetable_iter[line.id])
            except StopIteration:
                return all_departures
            self.new_departures(time, dt, line, all_departures)

        next_time = time.add_time(dt)
        if time <= self._current_time_table[line.id] < next_time:
            all_departures.append(self._next_veh_departure[line.id][1])
            self.vehicles[line.id].appendleft(self._next_veh_departure[line.id][1])
            self._current_time_table[line.id] = self._next_time_table[line.id]
            try:
                self._next_time_table[line.id] = next(self._timetable_iter[line.id])
                new_veh = self.fleet.create_waiting_vehicle(line.stops[0], line.stops[-1], veh_path)
                self._next_veh_departure[line.id] = (self._current_time_table[line.id], new_veh)
            except StopIteration:
                return all_departures
            self.new_departures(time, dt, line, all_departures)
        return all_departures

    def request_vehicle(self, user: "User", drop_node:str) -> None:
        start = user.path.nodes[0]

        for line in self.lines.values():
            if start in line.stops:
                user_line = line
                break
        else:
            log.error(f'{user} start is not in the PublicTransport mobility service {self.id}')
            sys.exit(-1)

        prev_line_node = user_line._rev_adjacency[start]
        if prev_line_node is None:
            departure_time, waiting_veh = user_line._next_veh_departure
            waiting_veh.take_next_user(user, drop_node)
            return
        else:
            curr_veh = None
            next_veh = None
            it_veh = iter(self.vehicles[user_line.id])
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
        for lid, line in self.lines.items():
            for new_veh in self.new_departures(self._tcurrent, dt, line):
                self.fleet.start_waiting_vehicle(new_veh.id)
                if self._observer is not None:
                    new_veh.attach(self._observer)

            self.clean_arrived_vehicles(lid)

    def service_level_costs(self, nodes:List[str]) -> CostDict:
        """
        Must return a dict of costs representing the cost of the service computed from a path
        Parameters
        ----------
        path

        Returns
        -------

        """
        return CostDict(waiting_time=0,
                        environmental=0,
                        currency=0)


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
        super(PublicTransportGraphLayer, self).__init__(id, veh_type, default_speed, services, observer)
        self.lines = dict()
        self.line_connexions = set()

    def add_mobility_service(self, service:"AbstractMobilityService"):
        assert isinstance(service, PublicTransportMobilityService), f"PublicTransportGraphLayer only accept mobility services with type PublicTransportMobilityService"
        super(PublicTransportGraphLayer, self).add_mobility_service(service)

    def add_line(self, lid: str, timetable: "TimeTable") -> Line:
        new_line = Line(lid, self, timetable)
        self.lines[lid] = new_line
        for service in self.mobility_services.values():
            timetable_iter = iter(timetable.table)
            service._timetable_iter[lid] = iter(timetable.table)
            service._current_time_table[lid] = next(timetable_iter)
            service._next_time_table[lid] = next(timetable_iter)

        return new_line

    def show_lines(self) -> None:
        print(self.lines)

    def connect_lines(self, ulineid: str, dlineid: str, nid: str, costs:dict=None, two_ways=True) -> None:
        assert self.lines[ulineid]._prefix(nid) in self.lines[ulineid].stops
        assert self.lines[dlineid]._prefix(nid) in self.lines[dlineid].stops
        c = {'time': self.lines[dlineid].timetable.get_freq() / 2, "length": 0}
        if costs is not None:
            c.update(costs)

        self._graph.add_link('_'.join([ulineid, dlineid, nid]),
                             ulineid + '_' + nid,
                             dlineid + '_' + nid,
                             c,
                             mobility_service=self.id)

        if two_ways:
            c = {'time': self.lines[ulineid].timetable.get_freq() / 2, "length": 0}
            if costs is not None:
                c.update(costs)
            self._graph.add_link('_'.join([dlineid, ulineid, nid]),
                                 dlineid + '_' + nid,
                                 ulineid + '_' + nid,
                                 c,
                                 mobility_service=self.id)
            self.line_connexions.add('_'.join([dlineid, ulineid, nid]))

    def connect_to_service(self, nid) -> dict:
        for line in self.lines.values():
            if nid in line.stops:
                return {"time": line.timetable.get_freq()/2}

    def __dump__(self) -> dict:
        return {"TYPE": ".".join([PublicTransportGraphLayer.__module__, PublicTransportGraphLayer.__name__]),
                "ID": self.id,
                "DEFAULT_SPEED": self.default_speed,
                "LINES": [l.__dump__() for l in self.lines.values()],
                "CONNECTIONS": [self._graph.get_link(l).__dump__() for l in self.line_connexions]}

    @classmethod
    def __load__(cls, data: dict) -> "PublicTransport":
        new_obj = cls(data['ID'], data["DEFAULT_SPEED"])
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
                                    l['COSTS'],
                                    l['REF_LINKS'],
                                    l['REF_LANE_IDS']) for l in ldata['LINKS']]
        return new_obj

    def update_costs(self, time:"Time"):
        """
        Update of the cost in PublicTransport links use only the travel time on the link with speed and length plus
        the frequency of the line divide by 2.
        :param time:
        :return:
        """
        for lid, line in self.lines.items():
            start_stop = line.start

            curr_stop = start_stop
            next_stop = line._adjacency[curr_stop]
            while next_stop is not None:
                curr_link = self._graph.links[(line._prefix(curr_stop), line._prefix(next_stop))]
                curr_link.costs['time'] = curr_link.costs['speed'] * curr_link.costs['length']
                curr_stop = next_stop
                next_stop = line._adjacency[curr_stop]

    def construct_veh_path(self, lid: str):
        veh_path = list()
        path = self.lines[lid].stops
        for i in range(len(path) - 1):
            unode = path[i]
            dnode = path[i+1]
            if self._graph.nodes[dnode].layer == self.id:
                key = (unode, dnode)
                veh_path.append((key, self._graph.links[key].costs['length']))
            else:
                break
        return veh_path

    def connect_to_layer(self, nid) -> dict:
        for line in self.lines.values():
            if nid in line.stops:
                return {"wating_time": line._timetable.get_freq() / 2}


class BusMobilityGraphLayer(PublicTransportGraphLayer):
    def __init__(self, id:str, default_speed:float, services:List[AbstractMobilityService]=None, observer=None):
        super(BusMobilityGraphLayer, self).__init__(id, Bus, default_speed, services, observer)


class MetroMobilityGraphLayer(PublicTransportGraphLayer):
    def __init__(self, id:str, default_speed:float, services:List[AbstractMobilityService]=None, observer=None):
        super(MetroMobilityGraphLayer, self).__init__(id, Metro, default_speed, services, observer)
