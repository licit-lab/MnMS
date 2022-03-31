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
        self._mobility_graph = None
        self.users:Dict[str, User] = dict()
        self._transiting = set()
        self._walking = dict()
        self._walk_speed = walk_speed
        self._tcurrent = None

    def set_graph(self, mmgraph:MultiModalGraph):
        self._graph = mmgraph

    def set_time(self, time:Time):
        self._tcurrent = time.copy()
        self._mobility_graph = self._graph.mobility_graph

    def update_time(self, dt:Dt):
        self._tcurrent = self._tcurrent.add_time(dt)

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
            user._current_node = upath[cnode_ind+1]
            user._current_link = (user._current_node, upath[upath.index(user._current_node)+1])
            user._remaining_link_length = self._mobility_graph.links[user._current_link].costs['length']
            del self._walking[user.id]
            self._transiting.add(user.id)

            self._request_user_vehicles(user)

    def _process_user(self):
        to_del = list()
        arrived_user = list()
        for uid in self._transiting:
            user = self.users[uid]
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
                    self._walking[uid] = next_link.costs['length']
                    to_del.append(uid)
                elif isinstance(next_link, ConnectionLink):
                    self._request_user_vehicles(user)

        for uid in to_del:
            self._transiting.remove(uid)

        for uid in arrived_user:
            del self.users[uid]

    def _request_user_vehicles(self, user:User):
        upath = user.path.nodes

        # Setting user initial position
        start_node = self._mobility_graph.nodes[user._current_node]
        start_node_pos = self._graph.flow_graph.nodes[start_node.reference_node].pos
        user._position = start_node_pos

        # Finding the mobility service associated and request vehicle
        ind_node_start = upath.index(user._current_node)
        for ilayer, (layer, slice_nodes) in enumerate(user.path.layers):
            if slice_nodes.start <= ind_node_start < slice_nodes.stop:
                mservice_id = user.path.mobility_services[ilayer]
                mservice = self._graph.layers[layer].mobility_services[mservice_id]
                log.info(f"Stop {upath[slice_nodes][-1]}, {upath}, {upath[slice_nodes]}")
                mservice.request_vehicle(user, upath[slice_nodes][-1])
                break
        else:
            log.warning(f"No mobility service found for user {user}")

    def step(self, dt:Dt, new_users:List[User]):
        log.info(f"Step User Flow {self._tcurrent}")

        for user in new_users:
            self.users[user.id] = user
            self._transiting.add(user.id)

        self._process_user()
        self._user_walking(dt)
