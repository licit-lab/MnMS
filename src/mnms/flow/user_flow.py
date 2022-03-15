from typing import Dict, List

from mnms.graph.core import MultiModalGraph, TransitLink
from mnms.demand.user import User
from mnms.graph.elements import ConnectionLink
from mnms.tools.time import Dt, Time
from mnms.log import create_logger

log = create_logger(__name__)


class UserFlow(object):
    def __init__(self, walk_speed=1.42):
        self._graph: MultiModalGraph = None
        self.users:Dict[str, User] = dict()
        self._transiting = dict()
        self._walking = dict()
        self._walk_speed = walk_speed
        self._tcurrent = None

    def set_graph(self, mmgraph:MultiModalGraph):
        self._graph = mmgraph

    def set_time(self, time:Time):
        self._tcurrent = time.copy()

    def update_time(self, dt:Dt):
        self._tcurrent = self._tcurrent.add_time(dt)

    def initialize(self):
        self._mobility_graph = self._graph.mobility_graph

    def _user_walking(self, dt:Dt):
        finish_walk = list()
        for uid, remaining_length in self._walking.items():
            remaining_length -= dt.to_seconds() * self._walk_speed
            if remaining_length <= 0:
                finish_walk.append(self.users[uid])
            else:
                self._walking[uid] = remaining_length

        for user in finish_walk:
            upath = user.path.nodes
            cnode = user._current_node
            cnode_ind = upath.index(cnode)
            user._current_node = self._graph.mobility_graph.nodes[upath[cnode_ind+1]].id
            user._current_link = (user._current_node, upath[upath.index(user._current_node)+1])
            user._remaining_link_length = 0
            del self._walking[user.id]
            self._transiting[user.id] = user

        self._request_user_vehicles(finish_walk)

    def _process_user(self):
        to_del = list()
        arrived_user = list()
        for uid, user in self._transiting.items():
            upath = user.path.nodes
            if user._current_node == upath[-1]:
                log.info(f"{user} arrived to its destination")
                user.finish_trip(self._tcurrent)
                arrived_user.append(uid)
                to_del.append(uid)
            elif not user.is_in_vehicle and not user._waiting_vehicle:
                cnode = user._current_node
                cnode_ind = upath.index(cnode)
                next_link = self._graph.mobility_graph.links[(cnode, upath[cnode_ind+1])]
                if isinstance(next_link, TransitLink):
                    log.info(f"{user} enter connection on {next_link}")
                    self._walking[uid] = next_link.costs['time']
                    to_del.append(uid)
                elif isinstance(next_link, ConnectionLink):
                    self._request_user_vehicles([user])

        for uid in to_del:
            del self._transiting[uid]

        for uid in arrived_user:
            del self.users[uid]

    def _request_user_vehicles(self, new_users:List[User]):
        for nu in new_users:
            # nu.notify(nu.departure_time)
            upath = nu.path.nodes
            self.users[nu.id] = nu
            self._transiting[nu.id] = nu
            start_node = self._mobility_graph.nodes[nu._current_node]
            start_node_pos = self._graph.flow_graph.nodes[start_node.reference_node].pos
            nu._position = start_node_pos
            mservice_id = start_node.mobility_service
            mservice = self._graph._mobility_services[mservice_id]
            prev_service_id = mservice_id
            log.info(f"Request VEH for {nu} at {nu._current_node}")
            for i in range(upath.index(start_node.id)+1, len(upath)):
                current_service_id = self._mobility_graph.nodes[upath[i]].mobility_service
                if prev_service_id != current_service_id:
                    mservice.request_vehicle(nu, upath[i - 1])
                    break
                elif i == len(upath) - 1:
                    mservice.request_vehicle(nu, upath[i])
                    break

    def step(self, dt:Dt, new_users:List[User]):
        log.info(f"Step User Flow {self._tcurrent}")

        self._process_user()
        self._user_walking(dt)
        self._request_user_vehicles(new_users)

    def update_graph(self):
        pass
