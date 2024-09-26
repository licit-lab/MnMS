from typing import Dict, List, Optional

import numpy as np
import sys
import csv


from mnms.graph.layers import MultiLayerGraph
from mnms.demand.user import User, UserState
# from mnms.graph.core import ConnectionLink, TransitLink
from mnms.time import Dt, Time
from mnms.log import create_logger
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.travel_decision.abstract import Event

log = create_logger(__name__)


class UserFlow(object):
    def __init__(self, walk_speed: float=1.42, outfile: str=None):
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

        if outfile is None:
            self._write = False
        else:
            self._write = True
            self._outfile = open(outfile, "w")
            self._csvhandler = csv.writer(self._outfile, delimiter=';', quotechar='|')
            self._csvhandler.writerow(['ID', 'TRAVELED_NODES', 'TRAVELED_LINKS', 'TRAVELED_SERVICES'])

    def set_graph(self, mlgraph:MultiLayerGraph):
        """Method to associate a multi layer graph to a UserFlow object and sets
        the walking speed in the TransitLayer of this graph.

        Args:
            -mlgraph: multi layer graph on which users travel
        """
        self._graph = mlgraph
        self._graph.transitlayer.walk_speed = self._walk_speed

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
        unode, dnode = user.current_link
        remaining_length = user.remaining_link_length

        unode_pos = np.array(self._gnodes[unode].position)
        dnode_pos = np.array(self._gnodes[dnode].position)

        direction = dnode_pos - unode_pos
        norm_direction = np.linalg.norm(direction)
        if norm_direction > 0:
            normalized_direction = direction / norm_direction
            travelled = norm_direction - remaining_length
            user.position = unode_pos+normalized_direction*travelled

    def _user_walking(self, dt:Dt):
        """Method to manage users who are currently walking.

        Args:
            -dt: duration for which users walk (usually corresponds to the flow time step)
        """
        finish_walk_and_request = list()
        finish_walk = list()
        finish_trip = list()
        gnodes = self._graph.graph.nodes
        for uid in self._walking.keys():
            user = self.users[uid]
            if user.state == UserState.WALKING:
                upath = user.path.nodes
                dist_travelled = dt.to_seconds() * self._walk_speed
                arrival_time = self._tcurrent.copy()
                while dist_travelled > 0:
                    remaining_length = self._walking[uid]
                    if remaining_length <= dist_travelled:
                        # User arrived at the end of her current transit link
                        user.update_distance(remaining_length)
                        user.remaining_link_length = 0
                        arrival_time = arrival_time.add_time(Dt(seconds=remaining_length / self._walk_speed))
                        next_node = upath[user.get_current_node_index()+1]
                        user.update_achieved_path(next_node)
                        user.current_node = next_node
                        self.set_user_position(user)
                        user.notify(arrival_time)
                        if next_node == upath[-1]:
                            # User arrived at last node of her planned path
                            user.finish_trip(arrival_time)
                            finish_trip.append(user)
                            dist_travelled = 0
                        else:
                            # User still has way to go
                            if user.deadend_at_next_node:
                                # User stops walking
                                user.set_state_deadend(arrival_time)
                                finish_walk.append(user)
                                dist_travelled = 0
                            else:
                                cnode_ind = user.get_current_node_index()
                                next_next_node = upath[cnode_ind + 1]
                                next_link = gnodes[user.current_node].adj[next_next_node]
                                if next_link.label == 'TRANSIT':
                                    # User keeps walking
                                    log.info(f"User {uid} enters connection on {next_link.id}")
                                    dist_travelled = dist_travelled - remaining_length
                                    self._walking[uid] = next_link.length
                                    user.current_link = (user.current_node, next_next_node)
                                else:
                                    # User stops walking
                                    user.set_state_stop()
                                    finish_walk_and_request.append((user, arrival_time))
                                    dist_travelled = 0
                    else:
                        # User did not arrived at the end of current link
                        self._walking[uid] = remaining_length - dist_travelled
                        user.remaining_link_length = remaining_length - dist_travelled
                        self.set_user_position(user)
                        user.update_distance(dist_travelled)
                        dist_travelled = 0
            else:
                # User is not walking anymore for an external reason, e.g. DEADEND
                finish_walk.append(user)

        for user in finish_walk:
            del self._walking[user.id]

        for user, request_time in finish_walk_and_request:
            del self._walking[user.id]
            log.info(f'User {user.id} is about to request a vehicle because he has finished walking')
            user.set_state_waiting_answer()
            requested_mservice = self._request_user_vehicles(user, request_time)
            self._waiting_answer.setdefault(user.id, (user.response_dt.copy(),requested_mservice))

        for user in finish_trip:
            if self._write:
                self.write_result(user=user)
            del self.users[user.id]
            del self._walking[user.id]

    def _request_user_vehicles(self, user, request_time):
        """Method that formulates user's request to the proper mobility service.

        Args:
            -user: user who is about to request a service
            -request_time: time at which user requested the service

        Returns:
            -mservice: the mobility service to which the request was sent (None if
                       no relevant mobility service was found for the request)
        """
        if user.path is not None:
            upath = user.path.nodes

            start_node = self._gnodes[user.current_node]
            start_node_pos = start_node.position
            user.position = start_node_pos

            # Finding the mobility service associated and request vehicle
            ind_node_start = user.get_current_node_index()
            for ilayer, (layer, slice_nodes) in enumerate(user.path.layers):
                if slice_nodes.start == ind_node_start:
                    mservice_id = user.path.mobility_services[ilayer]
                    mservice = self._graph.layers[layer].mobility_services[mservice_id]
                    log.info(f"User {user.id} requests mobility service {mservice._id}")
                    mservice.add_request(user, upath[slice_nodes][-1], request_time)
                    user.requested_service = mservice
                    return mservice
            else:
                log.warning(f"No mobility service found for user {user.id}")
        else:
            log.warning(f'User {user.id} has no path, cannot find any mobility service '\
                'to which formulating a request.')
        return None

    def step(self, dt: Dt, new_users: List[User]):
        """Method corresponding to one step of the user flow module.

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
                cnode = u.current_node
                cnode_ind = u.get_current_node_index()
                next_link = self._gnodes[cnode].adj[upath[cnode_ind + 1]]
                u.position = self._gnodes[cnode].position
                if cnode == upath[-1]:
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
                    requested_mservice = self._request_user_vehicles(u, self._tcurrent)
                    self._waiting_answer.setdefault(u.id, (u.response_dt.copy(),requested_mservice))

                u.notify(self._tcurrent)

        for uid in to_del:
            if self._write:
                self.write_result(user=self.users[uid])
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

    def manage_links_removal_after_match(self, deleted_links, new_users, matched_user_id, service, decision_model):
        """Method that manages the interruption of users who were supposed to pass
        through a link that was deleted following a match.
        NB: For now only a match with a free-floating vehicle sharing service can
        lead to link deletion.

        Args:
            -deleted_links: the list of links that have been deleted
            -new_users: user who are about to depart but not yet taken into account
             by the user flow
            -matched_user_id: the id of the user who was matched
            -service: the mobility service with which user was matched
            -decision_model: the decision model for all users

        Returns:
            -users_canceling: users who should cancel their current request because
             they get interrupted
        """
        interrupted_users = []
        users_canceling = []
        for u in list(self.users.values()) + new_users:
            if u.id != matched_user_id and u.path is not None:
                unodes = u.path.nodes
                path_links = [(unodes[i],unodes[i+1]) for i in range(len(unodes)-1)]
                intersect = set(deleted_links).intersection(set(path_links))
                if len(intersect) > 0:
                    log.info(f"User {u.id} was supposed to pass through links {intersect} which were deleted, '\
                        f'trigger an INTERRUPTION event (current node = {u.current_node}, state = {u.state})")
                    interrupted_users.append(u)
                    # Clean eventual request already formulated by user to this service
                    if u.id in service._user_buffer.keys():
                        if u.state == UserState.WAITING_ANSWER:
                            # This user is waiting to be matched with a vehicle of the station we have just removed,
                            # turn her to STOP state, and save the fact that she should cancel her request
                            u.set_state_stop()
                        users_canceling.append(u.id)
        if interrupted_users:
            decision_model.add_users_for_planning(interrupted_users, [Event.INTERRUPTION]*len(interrupted_users))
            # NB: the planning will be called before the next user flow step so no need to interrupt user path now
        return users_canceling

    def write_result(self, user: User=None):
        """Method writing the results regarding users achieved path.

        Args:
            -user: user for which the achieved path should be written, if None,
             results are written for all users currently in the user flow.
        """
        if user is None:
            for uid,u in self.users.items():
                self._csvhandler.writerow([uid, " ".join(u.achieved_path),
                    " ".join(self.build_achieved_path_links(u.achieved_path)),
                    " ".join(u.achieved_path_ms)])
        else:
            self._csvhandler.writerow([user.id, " ".join(user.achieved_path),
                " ".join(self.build_achieved_path_links(user.achieved_path)),
                " ".join(user.achieved_path_ms)])

    def build_achieved_path_links(self, path_nodes):
        """Method to convert a list of nodes into a list of links.

        Args:
            -path_nodes: the list of nodes
        """
        links = []
        for i in range(len(path_nodes)-1):
            try:
                link = self._gnodes[path_nodes[i]].adj[path_nodes[i+1]]
                links.append(link.id)
            except:
                log.error(f'Cannot find link between {path_nodes[i]} and {path_nodes[i+1]}...')
        return links

    def finalize(self):
        if self._write:
            self._outfile.close()
