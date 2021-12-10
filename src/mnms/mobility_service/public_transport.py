import json
from collections import defaultdict

from mnms.mobility_service.shared import SharedMoblityService
from mnms.graph.core import TopoNode, ConnectionLink, TransitLink


class Line(object):
    def __init__(self, id: str, mobility_service: "PublicTransport", timetable: "TimeTable"):
        self.id = id
        self.timetable = timetable
        self.stops = set()
        self.links = set()
        self.mobility_service = mobility_service
        self.service_id = mobility_service.id

        self._adjacency = defaultdict(lambda: None)

        self.start = None
        self.end = None

    def add_stop(self, sid:str, ref_node:str=None) -> None:
        self.mobility_service.add_node(self._update_name(sid), ref_node)
        self.stops.add(sid)

    def add_start_stop(self, sid: str, ref_node:str):
        self.start = sid
        self.add_stop(sid, ref_node)

    def add_end_stop(self, sid:str, ref_node:str):
        self.end = sid
        self.add_stop(sid, ref_node)

    def connect_stops(self, lid:str, up_sid: str, down_sid: str, length:float, costs={}, reference_links=None,
                      reference_lane_ids=None) -> None:
        assert up_sid in self.stops
        assert down_sid in self.stops
        costs.update({'length': length})
        self.mobility_service.add_link(self._update_name(lid),
                                       self._update_name(up_sid),
                                       self._update_name(down_sid),
                                       costs=costs,
                                       reference_links=reference_links,
                                       reference_lane_ids=reference_lane_ids)
        self.links.add(lid)
        self._adjacency[up_sid] = down_sid

    def _update_name(self, name):
        return self.id+'_'+name


class PublicTransport(SharedMoblityService):
    def __init__(self, id:str, default_speed:float):
        super(PublicTransport, self).__init__(id, default_speed)
        self.lines = dict()
        self.line_connexions = []

    def add_line(self, lid: str, timetable: "TimeTable") -> Line:
        new_line = Line(lid, self, timetable)
        self.lines[lid] = new_line
        return new_line

    def show_lines(self) -> None:
        print(self.lines)

    def connect_lines(self, uline: str, dline: str, nid: str, costs={}, two_ways=True) -> None:
        assert nid in self.lines[uline].stops
        assert nid in self.lines[dline].stops
        c = {'time': self.lines[dline].timetable.get_freq()/2, "length": 0}
        c.update({"length":0})
        c.update(costs)

        self.add_link('_'.join([uline, dline, nid]),
                      uline+'_'+nid,
                      dline+'_'+nid,
                      c)

        if two_ways:
            c = {'time': self.lines[uline].timetable.get_freq()/2, "length": 0}
            c.update(costs)
            self.add_link('_'.join([dline, uline, nid]),
                          dline+'_'+nid,
                          uline+'_'+nid,
                          c)


    def update_costs(self, time:"Time"):
        for lid, line in self.lines.items():
            # print(line._adjacency)
            start_stop = line.start
            freq = line.timetable.get_freq()
            assert freq is not None

            curr_stop = start_stop
            next_stop = line._adjacency[curr_stop]
            while next_stop is not None:
                # print(curr_stop, next_stop)
                curr_link = self.links[(line._update_name(curr_stop), line._update_name(next_stop))]
                curr_link.costs['time'] = curr_link.costs['speed'] * curr_link.costs['length'] + freq/2

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

    service = PublicTransport("TEST")

    line0 = service.add_line('L0')
    line0.add_stop("0", "00")
    line0.add_stop("1", "11")

    line0.connect_stops('0_1', '0', '1', {'test': 32}, ['0_1'], [2])

    line1 = service.add_line('TEST2')
    line1.add_stop("1", "11")
    line1.add_stop("33", "5")
    line1.connect_stops('32_33', '32', '33', {'test': 2}, ['0_99'], [0])

    service.connect_lines('L0', 'TEST2', '1', {'test': 0})

    # print(json.dumps(service.dump_json(), indent=1))


    # tram = PublicTransport('Tram')
    # l0 = tram.add_line('L0')
    # l0.add_stop('0')
    #
    #
    # mmgraph = MultiModalGraph(nodes=nodes,
    #                           links=links,
    #                           mobility_services=[bus])

