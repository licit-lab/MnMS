from typing import Dict, List

from mnms.graph.core import MultiModalGraph
from mnms.demand.user import User
from mnms.tools.time import Dt, Time
from mnms.log import create_logger

log = create_logger(__name__)


class UserFlow(object):
    def __init__(self, walk_speed=1.42):
        self._graph: MultiModalGraph = None
        self.users:Dict[str, User] = dict()
        self._waiting = dict()
        self._walking = dict()
        self._walk_speed = 1.42
        self._tcurrent = None

    def set_graph(self, mmgraph:MultiModalGraph):
        self._graph = mmgraph

    def set_time(self, time:Time):
        self._tcurrent = time.copy()

    def update_time(self, dt:Dt):
        self._tcurrent = self._tcurrent.add_time(dt)

    def initialize(self):
        self._mobility_graph = self._graph.mobility_graph

    def step(self, dt:Dt, new_users:List[User]):
        log.info(f"Step User Flow {self._tcurrent}")
        arrived_user = set()

        zero_dt = Dt()

        for nu in new_users:
            start_node = self._mobility_graph.nodes[nu.path[0]]
            mservice = self._graph._mobility_services[start_node.mobility_service]
            waiting_time, node, veh = mservice.request_vehicle(nu)

            if waiting_time == zero_dt:
                if node == nu.path[0]:
                    veh.take_user(nu)
                else:
                    self._waiting[nu.id] = waiting_time
                    self.users[nu.id] = nu
            else:
                self._waiting[nu.id] = waiting_time

        uwait_to_del = list()
        for uid, uwait in self._waiting.items():
            if uwait.to_seconds() - dt.to_seconds() <= 0:
                uwait_to_del.append(uid)
            else:
                self._waiting[uid] = uwait - dt

        for u in uwait_to_del:
            del self._waiting[u]

        pass

    def update_graph(self):
        pass
