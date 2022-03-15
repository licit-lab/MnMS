from copy import deepcopy
from random import sample

import numpy as np

from mnms.demand import User
from mnms.graph.elements import TopoNode, ConnectionLink
from mnms.graph.shortest_path import bidirectional_dijkstra, dijkstra
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.log import create_logger
from mnms.tools.exceptions import PathNotFound
from mnms.tools.time import Time, Dt
from mnms.vehicles.veh_type import Car

log = create_logger(__name__)


class OnDemandService(AbstractMobilityService):
    def __init__(self, id:str, default_speed:float, attached_service: AbstractMobilityService, veh_type=Car):
        super(OnDemandService, self).__init__(id, veh_type, default_speed)
        self._is_duplicate = True
        self.depots = []

        for node in attached_service._graph.nodes.values():
            new_node = TopoNode(self._prefix(node.id),
                                self.id,
                                node.reference_node)
            self._graph._add_node(new_node)

        for link in attached_service._graph.links.values():
            new_link = ConnectionLink(self._prefix(link.id),
                                      self._prefix(link.upstream_node),
                                      self._prefix(link.downstream_node),
                                      deepcopy(link.costs),
                                      deepcopy(link.reference_links),
                                      deepcopy(link.reference_lane_ids),
                                      self.id)
            self._graph._add_link(new_link)

        self._waiting_vehicle = dict()

    def _prefix(self, id:str):
        return f"{self.id}_{id}"

    def random_distribution_vehicles(self, n_veh:int):
        for n in sample(list(self._graph.nodes), n_veh):
            veh = self.fleet.create_waiting_vehicle(n, None, [])
            self._waiting_vehicle[veh.id] = veh

    def create_waiting_vehicle(self, node: str):
        assert self._prefix(node) in self._graph.nodes
        veh = self.fleet.create_waiting_vehicle(self._prefix(node), None, [])
        if self._observer is not None:
            veh.attach(self._observer)
        self._waiting_vehicle[veh.id] = veh

    def update_costs(self, time: Time):
        pass

    def connect_to_service(self, nid) -> dict:
        return {}

    def __dump__(self) -> dict:
        return {"TYPE": ".".join([PersonalCar.__module__, PersonalCar.__name__]),
                "ID": self.id,
                "DEFAULT_SPEED": self.default_speed,
                "NODES": [n.__dump__() for n in self._graph.nodes.values()],
                "LINKS": [l.__dump__() for l in self._graph.links.values()]}

    @classmethod
    def __load__(cls, data: dict) -> "PersonalCar":
        new_obj = cls(data['ID'], data["DEFAULT_SPEED"])
        [new_obj._graph._add_node(TopoNode.__load__(ndata)) for ndata in data['NODES']]
        [new_obj._graph._add_link(ConnectionLink.__load__(ldata)) for ldata in data['LINKS']]
        return new_obj

    def update(self, dt:Dt):
        for veh in list(self.fleet.vehicles.values()):
            if veh.is_arrived:
                log.info(f'Make vehicle {veh.id} waits at {veh.current_link[1]}')
                veh.origin = veh.current_link[1]
                veh.is_arrived = False
                self.fleet.make_vehicle_wait(veh)

    def request_vehicle(self, user: User, drop_node:str) -> None:
        user.available_mobility_service = frozenset([self.id])

        upos = user.position
        upath = list(user.path.nodes)
        if self.fleet.nb_waiting_vehicles > 0:
            vehicles = list(self.fleet._waiting.values())
            veh_pos = np.array([v.position for v in vehicles])
            dist_vector = np.linalg.norm(veh_pos-upos, axis=1)

            nearest_veh_index = np.argmin(dist_vector)
            nearest_veh = vehicles[nearest_veh_index]
            nearest_veh.destination = user.current_node
            log.info(f"Compute veh path to user {nearest_veh.origin} -> {user.current_node}")
            veh_path = bidirectional_dijkstra(self._graph, nearest_veh.origin, user.current_node, 'time', None)
            if veh_path.cost == float('inf'):
                raise PathNotFound(nearest_veh.origin, user.current_node)
            log.info(f"{self.id} set VEH path: {veh_path}")
            veh_path = self._construct_veh_path(list(veh_path.nodes)[:-1]+upath[upath.index(user._current_node):upath.index(drop_node)+1])
            log.info(f"{self.id} set VEH path: {veh_path}")
            nearest_veh.set_path(veh_path)
            nearest_veh.take_next_user(user, drop_node)

            self.fleet.start_waiting_vehicle(nearest_veh.id)


if __name__ == "__main__":
    from mnms.graph.core import MultiModalGraph
    from mnms.mobility_service.personal_car import PersonalCar
    from mnms.demand import BaseDemandManager
    from mnms.travel_decision import BaseDecisionModel
    from mnms.simulation import Supervisor
    from mnms.flow import MFDFlow

    mmgraph = MultiModalGraph()

    mmgraph.flow_graph.add_node('0', [0, 0])
    mmgraph.flow_graph.add_node('1', [100, 0])
    mmgraph.flow_graph.add_node('2', [200, 0])
    mmgraph.flow_graph.add_node('3', [300, 0])
    mmgraph.flow_graph.add_node('4', [400, 0])
    mmgraph.flow_graph.add_node('5', [500, 0])

    mmgraph.flow_graph.add_link('0_1', '0', '1')
    mmgraph.flow_graph.add_link('1_2', '1', '2')
    mmgraph.flow_graph.add_link('2_3', '2', '3')
    mmgraph.flow_graph.add_link('3_4', '3', '4')
    mmgraph.flow_graph.add_link('4_5', '4', '5')

    car = PersonalCar('Car', 10)
    car.add_node('C0', '0')
    car.add_node('C1', '1')
    car.add_node('C2', '2')
    car.add_node('C3', '3')
    car.add_node('C4', '4')
    car.add_node('C5', '5')

    car.add_link('C0_C1', 'C0', 'C1', {'time': 5, 'length': 100}, reference_links=['0_1'])
    car.add_link('C1_C2', 'C1', 'C2', {'time': 5, 'length': 100}, reference_links=['1_2'])
    car.add_link('C2_C3', 'C2', 'C3', {'time': 5, 'length': 100}, reference_links=['2_3'])
    car.add_link('C3_C4', 'C3', 'C4', {'time': 5, 'length': 100}, reference_links=['3_4'])
    car.add_link('C4_C5', 'C4', 'C5', {'time': 5, 'length': 100}, reference_links=['4_5'])

    uber = OnDemandService('Uber', 10, car)
    uber.attach_vehicle_observer()
    uber.create_waiting_vehicle('C0')

    # mmgraph.add_mobility_service(uber)
    mmgraph.add_mobility_service(car)

    demand = BaseDemandManager([User('U0', '3', '5', Time('00:00:01'), available_mobility_services=['WALK', 'Uber'])])
    travel = BaseDecisionModel(mmgraph, cost='length')
    travel._radius_sp = 10

    supervisor = Supervisor(graph=mmgraph,
                            flow_motor=MFDFlow(),
                            demand=demand,
                            decision_model=travel)

    supervisor.run(Time('00:00:00'), Time('10:00:00'), Dt(seconds=2), 10)




    # uber._waiting_vehicle['0'].set_position(np.array([0, 0]))
    #
    # user =
    # user.set_position(('C3', 'C4'), 100, np.array([300, 0]))
    # user._current_node = 'C3'
    #
    # user.path = dijkstra(car._graph, 'C3', 'C5', 'time', None)
    #
    # uber.request_vehicle(user, 'C5')




