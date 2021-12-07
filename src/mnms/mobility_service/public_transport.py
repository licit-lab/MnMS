from mnms.mobility_service.abstract import BaseMobilityService
from mnms.graph.core import TopoLink, TopoNode


class Line(object):
    def __init__(self, id: str, mobility_service: "PublicTransport"):
        self.id = id
        self.mobility_service = mobility_service
        self.service_id = mobility_service.id

        self.stops = set()
        self.links = set()

    def add_stop(self, sid:str, ref_node:str=None) -> None:
        new_node = TopoNode(sid, self.service_id, ref_node)
        self.mobility_service._nodes.append(new_node)
        self.stops.add(sid)

    def connect_stops(self, lid:str, up_sid: str, down_sid: str, costs=None, reference_links=None,
                      reference_lane_ids=None) -> None:

        new_link = TopoLink(lid, up_sid, down_sid, costs=costs, reference_links=reference_links,
                        reference_lane_ids=reference_lane_ids, mobility_service=self.service_id)
        self.mobility_service._links.append(new_link)
        self.links.add(lid)


class PublicTransport(BaseMobilityService):
    def __init__(self, id:str):
        super(PublicTransport, self).__init__(id)
        self.lines = []

    def add_line(self, lid: str) -> Line:
        new_line = Line(lid, self)
        self.lines.append(new_line)
        return new_line

    def show_lines(self) -> None:
        print(list(self.lines.keys()))

    def connect_lines(self, up_line: str, down_line: str, costs={}) -> None:
        costs.update({"length":0})
        new_link = TopoLink(lid, up_sid, down_sid, costs=costs, reference_links=reference_links,
                            reference_lane_ids=reference_lane_ids, mobility_service=self.service_id)
        self.mobility_service._links.append(new_link)
        self.links.add(lid)




if __name__ == "__main__":

    from mnms.graph.core import MultiModalGraph

    mmgraph = MultiModalGraph()

    mmgraph.flow_graph.add_node('0', [0, 0])
    mmgraph.flow_graph.add_node('1', [1, 0])
    mmgraph.flow_graph.add_node('2', [1, 1])
    mmgraph.flow_graph.add_node('3', [0, 1])

    mmgraph.flow_graph.add_link('0_1', '0', '1')
    mmgraph.flow_graph.add_link('1_2', '1', '2')
    mmgraph.flow_graph.add_link('2_3', '2', '3')
    mmgraph.flow_graph.add_link('3_0', '3', '0')


    bus = PublicTransport('Bus')

    l0 = bus.add_line('L0')
    l0.add_stop('L0_0', '0')
    l0.add_stop('L0_1', '2')
    l0.connect_stops('L0_0_1', 'L0_0', 'L0_1', reference_links=['0_1', '1_2'])

    l1 = bus.add_line('L1')
    l1.add_stop('L1_0', '3')
    l1.add_stop('L1_1', '0')
    l1.connect_stops('L1_0_1', 'L1_0', 'L1_1', reference_links=['3_0'])

    bus.update_graph(mmgraph)

