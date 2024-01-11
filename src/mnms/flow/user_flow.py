from typing import Dict, List, Optional

import numpy as np
import sys


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
        Manage the motion and state update of users.

        Args:
            -walk_speed: The speed of the User walk
        """
        self._graph: Optional[MultiLayerGraph] = None
        self.users:Dict[str, User] = dict()
        self._walking: Dict = dict()
        self._walk_speed: float = walk_speed
        self._tcurrent: Optional[Time] = None

        self._waiting_answer: Dict[str, tuple[Time, AbstractMobilityService]] = dict()

        self._gnodes = None

    def set_graph(self, mlgraph:MultiLayerGraph):
        """Method to associate a multi layer graph to a UserFlow object.

        Args:
            -mlgraph: multi layer graph on which users travel
        """
        self._graph = mlgraph

    def set_time(self, time:Time):
        """Method to set current time for the UserFlow module.

        Args:
            -time: current time
        """
        self._tcurrent = time.copy()

    def update_time(self, dt:Dt):
        """Method to update current time of the UserFlow module.

        Args:
            -dt: duration to add to current time
        """
        self._tcurrent = self._tcurrent.add_time(dt)

    def set_user_position(self, user: User):
        """Method to move/update the position of a user.

        Args:
            -user: user to move
        """
        unode, dnode = user._current_link
        remaining_length = user._remaining_link_length

        unode_pos = np.array(self._gnodes[unode].position)
        dnode_pos = np.array(self._gnodes[dnode].position)

        direction = dnode_pos - unode_pos
        norm_direction = np.linalg.norm(direction)
        if norm_direction > 0:
            normalized_direction = direction / norm_direction
            travelled = norm_direction - remaining_length
            user.set_position_only(unode_pos+normalized_direction*travelled)

    def _user_walking(self, dt:Dt):
        """Method to manage users who are currently walking.

        Args:
            -dt: duration for which users walk (usually corresponds to the flow time step)
        """
        finish_walk = list()
        finish_trip = list()
        graph = self._graph.graph
        for uid in self._walking.keys():
            user = self.users[uid]
            upath = user.path.nodes
            dist_travelled = dt.to_seconds() * self._walk_speed
            arrival_time = self._tcurrent.copy()
            while dist_travelled > 0:
                remaining_length = self._walking[uid]
                if remaining_length <= dist_travelled:
                    # User arrived at the end of her current transit link
                    user.update_distance(remaining_length)
                    user.set_remaining_link_length(0)
                    arrival_time = arrival_time.add_time(Dt(seconds=remaining_length / self._walk_speed))
                    next_node = upath[user.get_current_node_index()+1]
                    user.set_current_node(next_node)
                    self.set_user_position(user)
                    user.notify(arrival_time.time)
                    if next_node == upath[-1]:
                        # User arrived at last node of her planned path
                        user.finish_trip(arrival_time)
                        finish_trip.append(user)
                        dist_travelled = 0
                    else:
                        # User still has way to go
                        cnode_ind = user.get_current_node_index()
                        next_next_node = upath[cnode_ind + 1]
                        next_link = graph.nodes[user._current_node].adj[next_next_node]
                        if next_link.label == 'TRANSIT':
                            # User keeps walking
                            log.info(f"User {uid} enters connection on {next_link.id}")
                            dist_travelled = dist_travelled - remaining_length
                            self._walking[uid] = next_link.length
                            user.set_current_link((user._current_node, next_next_node))
                        else:
                            # User stops walking
                            user.set_state_stop()
                            finish_walk.append(user)
                            dist_travelled = 0
                else:
                    # User did not arrived at the end of current link
                    self._walking[uid] = remaining_length - dist_travelled
                    user.set_remaining_link_length(remaining_length - dist_travelled)
                    self.set_user_position(user)
                    user.update_distance(dist_travelled)
                    dist_travelled = 0

        for user in finish_walk:
            del self._walking[user.id]
            log.info(f'User {user.id} is about to request a vehicle because he has finished walking')
            user.set_state_waiting_answer()
            requested_mservice = self._request_user_vehicles(user)
            self._waiting_answer.setdefault(user.id, (user.response_dt.copy(),requested_mservice))

        for u in finish_trip:
            del self.users[u.id]
            del self._walking[u.id]

    def _request_user_vehicles(self, user):
        """Method that formulates user's request to the proper mobility service.

        Args:
            -user: user who is about to request a service

        Returns:
            -mservice: the mobility service to which the request was sent (None if
                       no relevant mobility service was found for the request)
        """
        if user.path is not None:
            upath = user.path.nodes

            start_node = self._gnodes[user._current_node]
            start_node_pos = start_node.position
            user.set_position_only(start_node_pos)

            # Finding the mobility service associated and request vehicle
            ind_node_start = user.get_current_node_index()
            for ilayer, (layer, slice_nodes) in enumerate(user.path.layers):
                if slice_nodes.start == ind_node_start:
                    mservice_id = user.path.mobility_services[ilayer]
                    mservice = self._graph.layers[layer].mobility_services[mservice_id]
                    log.info(f"User {user.id} requests mobility service {mservice._id}")
                    mservice.add_request(user, upath[slice_nodes][-1])
                    return mservice
            else:
                log.warning(f"No mobility service found for user {user.id}")
        else:
            log.warning(f'User {user.id} has no path, cannot find any mobility service '\
                'to which formulating a request.')
        return None

    def step(self, dt: Dt, new_users: List[User]):
        """Method correponding to one step of the user flow module.

        Args:
            -dt: time step duration (usually corresponds to one flow time step duration)
            -new_users: list of users that are departing during this time step

        Returns:
            -refused_users: the list of users who can be considered as refused by the
                            mobility service they requested
        """
        log.info(f"Step User Flow {self._tcurrent}")
        self._gnodes = self._graph.graph.nodes

        refused_user = self.check_user_waiting_answers(dt)

        for u in new_users:
            if u.path is not None:
                self.users[u.id] = u

        self.determine_user_states()

        self._user_walking(dt)

        return refused_user

    def determine_user_states(self):
        """Method to manage users who are in STOP state.
        """
        to_del = list()
        for u in self.users.values():
            if u.state is UserState.STOP and u.path is not None:
                upath = u.path.nodes
                cnode = u._current_node
                cnode_ind = u.get_current_node_index()
                next_link = self._gnodes[cnode].adj[upath[cnode_ind + 1]]
                u.set_position_only(self._gnodes[cnode].position)
                if u._current_node == upath[-1]:
                    # User finished her planned trip, arrived at destination
                    u.finish_trip(self._tcurrent)
                    to_del.append(u.id)
                    self._walking.pop(u.id, None)
                    u.notify(self._tcurrent)
                elif next_link.label == "TRANSIT":
                    # User is about to walk
                    log.info(f"User {u.id} enters connection on {next_link.id}")
                    u.set_state_walking()
                    self._walking[u.id] = next_link.length
                else:
                    # User is about to request a service
                    self._walking.pop(u.id, None)
                    u.set_state_waiting_answer()
                    log.info(f'User {u.id} is about to request a vehicle because he is stopped')
                    requested_mservice = self._request_user_vehicles(u)
                    self._waiting_answer.setdefault(u.id, (u.response_dt.copy(),requested_mservice))

                u.notify(self._tcurrent)

        for uid in to_del:
            self.users.pop(uid)

    def check_user_waiting_answers(self, dt: Dt):
        """Method to manage users who are waiting an answer from a mobility service.

        Args:
            -dt: duration for which users have been waiting since the last call of this method
                 (usually corresponds to a flow time step duration)
        """
        to_del = list()
        refused_users = list()

        for uid, (time, requested_mservice) in self._waiting_answer.items():
            if self.users[uid].state is UserState.WAITING_ANSWER:
                new_time = time.to_seconds() - dt.to_seconds()
                if new_time <= 0:
                    log.info(f"User {uid} waited answer too long, cancels request for {requested_mservice._id}")
                    requested_mservice.cancel_request(uid)
                    refused_users.append(self.users[uid])
                    # Interrupt user's path but keep user in the list of user_flow
                    self.users[uid].interrupt_path(self._tcurrent)
                    to_del.append(uid)
                else:
                    self._waiting_answer[uid] = (Time.from_seconds(new_time), requested_mservice)
            else:
                # User is not waiting answer anymore
                to_del.append(uid)

        for uid in to_del:
            self._waiting_answer.pop(uid)

        return refused_users
