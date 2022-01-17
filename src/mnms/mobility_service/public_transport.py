from collections import defaultdict
from copy import deepcopy

from mnms.mobility_service.shared import SharedMoblityService
from mnms.tools.time import TimeTable, Time

def _NoneDefault():
    return None

class Line(object):
    def __init__(self, id: str, mobility_service: "PublicTransport", timetable: "TimeTable"):
        self.id = id
        self.timetable = timetable
        self.stops = list()
        self.links = set()
        self.mobility_service = mobility_service
        self.service_id = mobility_service.id

        self._adjacency = defaultdict(_NoneDefault)

    def add_stop(self, sid:str, ref_node:str=None) -> None:
        self.mobility_service.add_node(self._prefix(sid), ref_node)
        self.stops.append(sid)

    def connect_stops(self, lid:str, up_sid: str, down_sid: str, length:float, costs=None, reference_links=None,
                      reference_lane_ids=None) -> None:
        assert up_sid in self.stops
        assert down_sid in self.stops
        costs = {} if costs is None else costs
        costs.update({'length': length})
        self.mobility_service.add_link(self._prefix(lid),
                                       self._prefix(up_sid),
                                       self._prefix(down_sid),
                                       costs=costs,
                                       reference_links=reference_links,
                                       reference_lane_ids=reference_lane_ids)
        self.links.add(lid)
        self._adjacency[up_sid] = down_sid


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
                "STOPS": [self.mobility_service.nodes[self._prefix(s)].__dump__() for s in stops],
                "LINKS":[self.mobility_service.links[self.mobility_service._map_lid_nodes[self._prefix(l)]].__dump__() for l in self.links]}


class PublicTransport(SharedMoblityService):
    def __init__(self, id:str, default_speed:float):
        super(PublicTransport, self).__init__(id, default_speed)
        self.lines = dict()
        self.line_connexions = set()

    def add_line(self, lid: str, timetable: "TimeTable") -> Line:
        new_line = Line(lid, self, timetable)
        self.lines[lid] = new_line
        return new_line

    def show_lines(self) -> None:
        print(self.lines)

    def connect_lines(self, ulineid: str, dlineid: str, nid: str, costs:dict=None, two_ways=True) -> None:
        assert nid in self.lines[ulineid].stops
        assert nid in self.lines[dlineid].stops
        c = {'time': self.lines[dlineid].timetable.get_freq() / 2, "length": 0}
        if costs is not None:
            c.update(costs)

        self.add_link('_'.join([ulineid, dlineid, nid]),
                      ulineid + '_' + nid,
                      dlineid + '_' + nid,
                      c)

        if two_ways:
            c = {'time': self.lines[ulineid].timetable.get_freq() / 2, "length": 0}
            if costs is not None:
                c.update(costs)
            self.add_link('_'.join([dlineid, ulineid, nid]),
                          dlineid + '_' + nid,
                          ulineid + '_' + nid,
                          c)
            self.line_connexions.add('_'.join([dlineid, ulineid, nid]))

    def connect_to_service(self, nid) -> dict:
        for line in self.lines.values():
            if nid in {line._prefix(s) for s in line.stops}:
                return {"time": line.timetable.get_freq()/2}

    def __dump__(self) -> dict:
        return {"TYPE": ".".join([PublicTransport.__module__, PublicTransport.__name__]),
                "ID": self.id,
                "DEFAULT_SPEED": self.default_speed,
                "LINES": [l.__dump__() for l in self.lines.values()],
                "CONNECTIONS": [self.links[self._map_lid_nodes[l]].__dump__() for l in self.line_connexions]}

    @classmethod
    def __load__(cls, data:dict) -> "BaseMobilityService":
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
                curr_link = self.links[(line._prefix(curr_stop), line._prefix(next_stop))]
                curr_link.costs['time'] = curr_link.costs['speed'] * curr_link.costs['length']
                curr_stop = next_stop
                next_stop = line._adjacency[curr_stop]





if __name__ == "__main__":

    from mnms.graph.core import MultiModalGraph
    import json

    nodes = {'0': [0, 0],
             '1': [1, 0],
             '2': [1, 1],
             '3': [0, 1]}

    links = {'0_1': ('0', '1'),
             '1_2': ('1', '2'),
             '2_3': ('2', '3'),
             '3_0': ('3', '0')}

    service = PublicTransport("TEST", 23)

    line0 = service.add_line('L0', TimeTable.create_table_freq("07:00:00", "14:00:00", delta_min=30))
    line0.add_stop("0", "00")
    line0.add_stop("1", "11")

    line0.connect_stops('0_1', '0', '1', 23, {'test': 32}, ['0_1'], [2])

    line1 = service.add_line('TEST2', TimeTable.create_table_freq("07:00:00", "14:00:00", delta_min=15))
    line1.add_stop("1", "11")
    line1.add_stop("33", "5")
    line1.connect_stops('32_33', '1', '33', 110, {'test': 2}, ['0_99'], [0])

    service.connect_lines('L0', 'TEST2', '1', {'test': 0})

    # print(json.dumps(service.__dump__(), indent=1))
    from pprint import pprint
    pprint(service.__dump__())

    # tram = PublicTransport('Tram')
    # l0 = tram.add_line('L0')
    # l0.add_stop('0')
    #
    #
    # mmgraph = MultiModalGraph(nodes=nodes,
    #                           links=links,
    #                           mobility_services=[bus])

