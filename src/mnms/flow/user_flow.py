from typing import Dict, List, Optional

import numpy as np


from mnms.graph.layers import MultiLayerGraph
from mnms.demand.user import User, UserState
# from mnms.graph.core import ConnectionLink, TransitLink
from mnms.time import Dt, Time
from mnms.log import create_logger
from mnms.mobility_service.abstract import AbstractMobilityService

log = create_logger(__name__)


class UserFlow(object):
    def __init__(self, walk_speed=1.42):
        """
        Manage the flow of the User (walking and)
        Args:
            walk_speed: The speed of the User walk
        """
        self._graph: Optional[MultiLayerGraph] = None
        self.users:Dict[str, User] = dict()
        self._walking: Dict = dict()
        self._walk_speed: float = walk_speed
        self._tcurrent: Optional[Time] = None

        self._waiting_answer: Dict[str, tuple[Time, AbstractMobilityService]] = dict()

        self._gnodes = None

    def set_graph(self, mmgraph:MultiLayerGraph):
        self._graph = mmgraph

    def set_time(self, time:Time):
        self._tcurrent = time.copy()

    def update_time(self, dt:Dt):
        self._tcurrent = self._tcurrent.add_time(dt)

    def set_user_position(self, user: User):
        unode, dnode = user._current_link
        remaining_length = user._remaining_link_length

        unode_pos = np.array(self._gnodes[unode].position)
        dnode_pos = np.array(self._gnodes[dnode].position)

        direction = dnode_pos - unode_pos
        norm_direction = np.linalg.norm(direction)
        if norm_direction > 0:
            normalized_direction = direction / norm_direction
            travelled = norm_direction - remaining_length
            user._position = unode_pos+normalized_direction*travelled

    def _user_walking(self, dt:Dt):
        finish_walk = list()
        finish_trip = list()
        graph = self._graph.graph
        for uid, remaining_length in self._walking.items():
            dist_travelled = dt.to_seconds() * self._walk_speed
            user = self.users[uid]
            upath = user.path.nodes
            if remaining_length <= dist_travelled:
                user.update_distance(remaining_length)
                user._remaining_link_length = 0
                arrival_time = self._tcurrent.add_time(Dt(seconds=remaining_length / self._walk_speed))
                next_node = upath[upath.index(user._current_node) + 1]
                user._current_node = next_node
                self.set_user_position(user)
                if next_node == upath[-1]:
                    # arrival_time = self._tcurrent.add_time(Dt(seconds=dt.to_seconds()-excess_dist/self._walk_speed))

                    # next_node = upath[upath.index(user._current_node) + 1]
                    # user._current_link = (user._current_node, next_node)
                    # user._current_node = upath[-1]
                    # user._remaining_link_length = 0

                    # self.set_user_position(user)
                    user.finish_trip(arrival_time)
                    user.set_state_arrived()
                    # user.notify(arrival_time.time)
                    finish_trip.append(user)
                else:
                    next_link = graph.nodes[user._current_node].adj[upath[upath.index(user._current_node) + 1]]
                    if next_link.label == 'TRANSIT':
                        # User keeps walking
                        log.info(f"User {user.id} enters connection on {next_link.id}")
                        user.set_state_walking()
                        excess_dist = dist_travelled - remaining_length
                        self._walking[user.id] = max(0, next_link.length - excess_dist)
                        if excess_dist > next_link.length:
                            log.warning(f'User {user.id} cannot walk through more than two links in one time step !')
                    else:
                        # self.set_user_position(user)
                        # log.info(remaining_length)
                        user.set_state_stop()
                        finish_walk.append(user)

                user.notify(arrival_time.time)

            else:
                self._walking[uid] = remaining_length - dist_travelled
                user._remaining_link_length = remaining_length
                self.set_user_position(user)
                user.update_distance(dist_travelled)

        for user in finish_walk:
            # upath = user.path.nodes
            # cnode = user._current_node
            # cnode_ind = upath.index(cnode)
            # user._current_node = graph.nodes[upath[cnode_ind+1]].id
            # user._current_link = (user._current_node, upath[upath.index(user._current_node)+1])
            # user._remaining_link_length = 0
            del self._walking[user.id]
            # self._transiting[user.id] = user

        for u in finish_walk:
            log.info(f'User {u.id} is about to request a vehicle because he has finished walking')
            u.set_state_waiting_answer()
            requested_mservice = self._request_user_vehicles(u)
            self._waiting_answer.setdefault(u.id, (u.response_dt.copy(),requested_mservice))

        for u in finish_trip:
            del self.users[u.id]
            del self._walking[u.id]

    # def _process_user(self):
    #     to_del = list()
    #     arrived_user = list()
    #     for uid, user in self._transiting.items():
    #         if user.path is not None:
    #             upath = user.path.nodes
    #             if user._current_node == upath[-1]:
    #                 log.info(f"{user} arrived to its destination")
    #                 user.finish_trip(self._tcurrent)
    #                 arrived_user.append(uid)
    #                 to_del.append(uid)
    #             elif not user.is_in_vehicle and not user._waiting_vehicle:
    #                 cnode = user._current_node
    #                 cnode_ind = upath.index(cnode)
    #                 # next_link = graph.links[(cnode, upath[cnode_ind+1])]
    #                 next_link = self._gnodes[cnode].adj[upath[cnode_ind+1]]
    #                 if next_link.label == "TRANSIT":
    #                     log.info(f"{user} enter connection on {next_link.id}")
    #                     self._walking[uid] = next_link.costs['travel_time']
    #                     to_del.append(uid)
    #                 else:
    #                     self._request_user_vehicles(user)
    #
    #     for uid in to_del:
    #         del self._transiting[uid]
    #
    #     for uid in arrived_user:
    #         del self.users[uid]

    def _request_user_vehicles(self, user):
        if user.path is not None:
            upath = user.path.nodes

            start_node = self._gnodes[user._current_node]
            start_node_pos = start_node.position
            user._position = start_node_pos

            # Finding the mobility service associated and request vehicle
            ind_node_start = upath.index(user._current_node)
            for ilayer, (layer, slice_nodes) in enumerate(user.path.layers):
                if slice_nodes.start <= ind_node_start < slice_nodes.stop:
                    mservice_id = user.path.mobility_services[ilayer]
                    mservice = self._graph.layers[layer].mobility_services[mservice_id]
                    log.info(f"{user} request {mservice._id}")
                    mservice.add_request(user, upath[slice_nodes][-1])
                    return mservice
            else:
                log.warning(f"No mobility service found for user {user}")

    # def step(self, dt:Dt, new_users:List[User]):
    #     log.info(f"Step User Flow {self._tcurrent}")
    #
    #     for user in new_users:
    #         self.users[user.id] = user
    #         self._transiting[user.id] = user
    #
    #     self._process_user()
    #     self._user_walking(dt)
        # self._request_user_vehicles(new_users)

    def step(self, dt: Dt, new_users: List[User]):
        log.info(f"Step User Flow {self._tcurrent}")
        self._gnodes = self._graph.graph.nodes

        refused_user = self.check_user_waiting_answers(dt)

        for u in new_users:
            if u.path is not None:
                self.users[u.id] = u

        self.determine_user_states()

        self._user_walking(dt)

        return refused_user
        # self._request_user_vehicles(new_users)

    def determine_user_states(self):
        to_del = list()
        for u in self.users.values():
            if u.state is UserState.STOP:
                upath = u.path.nodes
                cnode = u._current_node
                cnode_ind = upath.index(cnode)
                next_link = self._gnodes[cnode].adj[upath[cnode_ind + 1]]
                u._position = self._gnodes[cnode].position
                if u._current_node == upath[-1]:
                    log.info(f"{u} arrived to its destination")
                    u.finish_trip(self._tcurrent)
                    to_del.append(u.id)
                    u.set_state_arrived()
                    self._walking.pop(u.id, None)
                    to_del.append(u.id)
                elif next_link.label == "TRANSIT":
                    log.info(f"User {u.id} enters connection on {next_link.id}")
                    u.set_state_walking()
                    self._walking[u.id] = next_link.length
                else:
                    self._walking.pop(u.id, None)
                    u.set_state_waiting_answer()
                    log.info(f'User {u.id} is about to request a vehicle because he is stopped')
                    requested_mservice = self._request_user_vehicles(u)
                    self._waiting_answer.setdefault(u.id, (u.response_dt.copy(),requested_mservice))

                u.notify(self._tcurrent)

        for uid in to_del:
            self.users.pop(uid)

    def check_user_waiting_answers(self, dt: Dt):
        to_del = list()
        refused_users = list()

        for uid, (time, requested_mservice) in self._waiting_answer.items():
            if self.users[uid].state is UserState.WAITING_ANSWER:
                new_time = time.to_seconds() - dt.to_seconds()
                if new_time < 0:
                    log.info(f"User {uid} waited answer too long, cancels request for {requested_mservice._id}")
                    requested_mservice.cancel_request(uid)
                    refused_users.append(self.users[uid])
                    self.users[uid].set_state_stop()
                    self.users[uid].notify(self._tcurrent)
                    del self.users[uid]
                    to_del.append(uid)
                else:
                    self._waiting_answer[uid] = (Time.from_seconds(new_time), requested_mservice)
            else:
                to_del.append(uid)

        for uid in to_del:
            self._waiting_answer.pop(uid)

        return refused_users
