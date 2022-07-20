from typing import Dict, List

from mnms.graph.layers import MultiLayerGraph
from mnms.demand.user import User
# from mnms.graph.core import ConnectionLink, TransitLink
from mnms.time import Dt, Time
from mnms.log import create_logger

log = create_logger(__name__)


class UserFlow(object):
    def __init__(self, walk_speed=1.42):
        self._graph: MultiLayerGraph = None
        self.users:Dict[str, User] = dict()
        self._transiting = dict()
        self._walking = dict()
        self._walk_speed = walk_speed
        self._tcurrent = None

    def set_graph(self, mmgraph:MultiLayerGraph):
        self._graph = mmgraph

    def set_time(self, time:Time):
        self._tcurrent = time.copy()

    def update_time(self, dt:Dt):
        self._tcurrent = self._tcurrent.add_time(dt)

    def _user_walking(self, dt:Dt):
        finish_walk = list()
        finish_trip = list()
        graph = self._graph.graph
        for uid, remaining_length in self._walking.items():
            remaining_length -= dt.to_seconds() * self._walk_speed
            user = self.users[uid]
            upath = user.path.nodes
            if remaining_length <= 0:
                if user._current_node == upath[-2]:
                    arrival_time = self._tcurrent.remove_time(Dt(seconds=abs(remaining_length)/self._walk_speed))
                    user._current_link = (user._current_node, upath[upath.index(user._current_node) + 1])
                    user._current_node = upath[-1]
                    user._remaining_link_length = 0
                    user.finish_trip(arrival_time)
                    user.notify(arrival_time.time)
                    finish_trip.append(user)
                else:
                    log.info(remaining_length)
                    finish_walk.append(user)
            else:
                self._walking[uid] = remaining_length

        for user in finish_walk:
            upath = user.path.nodes
            cnode = user._current_node
            cnode_ind = upath.index(cnode)
            user._current_node = graph.nodes[upath[cnode_ind+1]].id
            user._current_link = (user._current_node, upath[upath.index(user._current_node)+1])
            user._remaining_link_length = 0
            del self._walking[user.id]
            self._transiting[user.id] = user

        [self._request_user_vehicles(u) for u in finish_walk]

        for u in finish_trip:
            del self.users[u.id]
            del self._walking[u.id]

    def _process_user(self):
        gnodes = self._graph.graph.nodes
        to_del = list()
        arrived_user = list()
        for uid, user in self._transiting.items():
            if user.path is not None:
                upath = user.path.nodes
                if user._current_node == upath[-1]:
                    log.info(f"{user} arrived to its destination")
                    user.finish_trip(self._tcurrent)
                    arrived_user.append(uid)
                    to_del.append(uid)
                elif not user.is_in_vehicle and not user._waiting_vehicle:
                    cnode = user._current_node
                    cnode_ind = upath.index(cnode)
                    # next_link = graph.links[(cnode, upath[cnode_ind+1])]
                    next_link = gnodes[cnode].adj[upath[cnode_ind+1]]
                    if next_link.label == "TRANSIT":
                        log.info(f"{user} enter connection on {next_link}")
                        self._walking[uid] = next_link.costs['travel_time']
                        to_del.append(uid)
                    else:
                        self._request_user_vehicles(user)

        for uid in to_del:
            del self._transiting[uid]

        for uid in arrived_user:
            del self.users[uid]

    def _request_user_vehicles(self, user):
        if user.path is not None:
            upath = user.path.nodes

            # Setting user initial position
            self.users[user.id] = user
            self._transiting[user.id] = user
            start_node = self._graph.graph.nodes[user._current_node]
            start_node_pos = start_node.position
            user._position = start_node_pos

            # Finding the mobility service associated and request vehicle
            ind_node_start = upath.index(user._current_node)
            for ilayer, (layer, slice_nodes) in enumerate(user.path.layers):
                if slice_nodes.start <= ind_node_start < slice_nodes.stop:
                    mservice_id = user.path.mobility_services[ilayer]
                    mservice = self._graph.layers[layer].mobility_services[mservice_id]
                    # log.info(f"Stop {upath[slice_nodes][-1]}, {upath}, {upath[slice_nodes]}")
                    mservice.request_vehicle(user, upath[slice_nodes][-1])
                    break
            else:
                log.warning(f"No mobility service found for user {user}")

    def step(self, dt:Dt, new_users:List[User]):
        log.info(f"Step User Flow {self._tcurrent}")

        for user in new_users:
            self.users[user.id] = user
            self._transiting[user.id] = user

        self._process_user()
        self._user_walking(dt)
        # self._request_user_vehicles(new_users)

    def update_graph(self):
        pass
