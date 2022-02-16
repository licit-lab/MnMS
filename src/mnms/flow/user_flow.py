from typing import Dict, List

from mnms.demand.user import User
from mnms.flow.abstract import AbstractFlowMotor
from mnms.tools.time import Dt


class UserFlow(AbstractFlowMotor):
    def __init__(self, walk_speed=1.42):
        super(UserFlow, self).__init__()
        self.users:Dict[str, User] = dict()
        self._waiting = dict()
        self._walking = dict()
        self._walk_speed = 1.42

    def initialize(self):
        self._mobility_graph = self._graph.mobility_graph

    def step(self, dt:float, new_users:List[User]):
        arrived_user = set()

        for nu in new_users:
            start_node = self._mobility_graph.nodes[nu.path[0]]
            mservice = self._graph._mobility_services[start_node.mobility_service]
            waiting_time, node, veh = mservice.request_vehicle(nu)

            if waiting_time == Dt():
                if node == nu.path[0]:
                    veh.take_user(nu)
                else:
                    self._waiting[nu.id] = waiting_time
                    self.users[nu.id] = nu

    def update_graph(self):
        pass
