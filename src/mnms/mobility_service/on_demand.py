from random import sample

import numpy as np

from mnms.demand import User
from mnms.graph.shortest_path import dijkstra
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.log import create_logger
from mnms.tools.time import Time, Dt
from mnms.vehicles.veh_type import Car

log = create_logger(__name__)


class OnDemandService(AbstractMobilityService):
    def __init__(self, id:str, default_speed:float, attached_service: AbstractMobilityService, veh_type=Car):
        super(OnDemandService, self).__init__(id, veh_type, default_speed)
        self.depots = []
        self.share_graph(attached_service)

        self._waiting_vehicle = dict()

    def random_distribution_vehicles(self, n_veh:int):
        for n in sample(list(self._graph.nodes), n_veh):
            self.create_waiting_vehicule(n)

    def create_waiting_vehicule(self, node: str):
        assert node in self._graph.nodes
        veh = self.fleet.create_waiting_vehicle(node, None, [])
        self._waiting_vehicle[veh.id] = veh

    def update_costs(self, time: Time):
        pass

    def connect_to_service(self, nid) -> dict:
        return {}

    def __dump__(self) -> dict:
        pass

    @classmethod
    def __load__(cls, data: dict):
        pass

    def update(self, dt:Dt):
        log.info(f'Update mobility service {self.id}')

    def request_vehicle(self, user: User, drop_node:str) -> None:
        upos = user.position
        upath = list(user.path.nodes)
        vehicles = list(self._waiting_vehicle.values())
        veh_pos = np.array([v.position for v in vehicles])
        dist_vector = np.linalg.norm(veh_pos-upos, axis=1)

        nearest_veh_index = np.argmin(dist_vector)
        nearest_veh = vehicles[nearest_veh_index]
        nearest_veh.destination = user.current_node
        veh_path = dijkstra(self._graph, nearest_veh.origin, user.current_node, 'time', None)
        veh_path = self._construct_veh_path(list(veh_path.nodes)[:-1]+upath[upath.index(user._current_node):upath.index(drop_node)+1])
        nearest_veh.set_path(veh_path)

        self.fleet.start_waiting_vehicle(nearest_veh.id)

    # def get_closest_vehicle(self, unode:str):
    #     upos = self.


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
    uber.create_waiting_vehicule('C0')

    mmgraph.add_mobility_service(uber)
    mmgraph.add_mobility_service(car)

    demand = BaseDemandManager([User('U0', '3', '5', Time('00:00:01'), available_mobility_services=['WALK', 'Uber'])])
    travel = BaseDecisionModel(mmgraph, cost='length')

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




