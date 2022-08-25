import sys
from collections import defaultdict, deque
from functools import cached_property
from typing import List, Dict, Tuple, Optional, Deque, Generator, Type, Union

from mnms.demand import User
from mnms.log import create_logger
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.time import Dt, Time
from mnms.tools.cost import create_service_costs
from mnms.tools.exceptions import VehicleNotFoundError
from mnms.vehicles.veh_type import VehicleActivityServing, Vehicle, VehicleActivityStop, VehicleActivityRepositioning, \
    VehicleState, VehicleActivityPickup, VehicleActivity

log = create_logger(__name__)


def _insert_in_activity(curr_activity, activity_pos, drop_node, drop_node_ind, take_node_ind, user, veh, veh_node_ind):
    if veh_node_ind == take_node_ind:
        serving_path = curr_activity.path[take_node_ind:drop_node_ind]
        serving_activity = VehicleActivityServing(node=drop_node,
                                                  path=serving_path,
                                                  user=user)
        new_activities = [serving_activity]

    else:
        pickup_path = curr_activity.path[veh_node_ind:take_node_ind]
        serving_path = curr_activity.path[take_node_ind:drop_node_ind]
        pickup_activity = VehicleActivityPickup(node=user._current_node,
                                                path=pickup_path,
                                                user=user)
        serving_activity = VehicleActivityServing(node=drop_node,
                                                  path=serving_path,
                                                  user=user)

        new_activities = [pickup_activity, serving_activity]
    curr_activity.modify_path(curr_activity.path[drop_node_ind + 1:])

    # Check if vehicle is stopped
    if veh.activity.state is not VehicleState.STOP:
        veh.activity = None
        for a in reversed(new_activities + [curr_activity]):
            veh.activities.insert(activity_pos, a)
        # veh.add_activities(new_activities + [curr_activity])
    else:
        for a in reversed(new_activities):
            veh.activities.insert(activity_pos, a)
        # veh.add_activities([new_activities])


class PublicTransportMobilityService(AbstractMobilityService):
    def __init__(self, _id: str, veh_capacity=50):
        super(PublicTransportMobilityService, self).__init__(_id, veh_capacity=veh_capacity, dt_matching=0,
                                                             dt_periodic_maintenance=0)
        self.vehicles: Dict[str, Deque[Vehicle]] = defaultdict(deque)
        self._timetable_iter: Dict[str, Generator[Time, None, None]] = dict()
        self._current_time_table: Dict[str, Time] = dict()
        self._next_time_table: Dict[str, Time] = dict()
        self._next_veh_departure: Dict[str, Optional[Tuple[Time, Vehicle]]] = defaultdict(lambda: None)

    @cached_property
    def lines(self):
        return self.layer.lines

    def clean_arrived_vehicles(self, lid: str):
        if len(self.vehicles[lid]) > 0:
            first_veh = self.vehicles[lid][-1]
            if first_veh.state is VehicleActivityStop:
                log.info(f"Deleting arrived veh: {first_veh}")
                self.vehicles[lid].pop()
                self.fleet.delete_vehicle(first_veh.id)
                self.clean_arrived_vehicles(lid)

    def construct_veh_path(self, lid):
        veh_path = list()
        path = self.lines[lid]['nodes']
        for i in range(len(path) - 1):
            unode = path[i]
            dnode = path[i + 1]
            key = (unode, dnode)
            link = self.graph.nodes[unode].adj[dnode]
            veh_path.append((key, link.length))
        return veh_path

    def new_departures(self, time, dt, lid: str, all_departures=None):
        veh_path = self.construct_veh_path(lid)
        end_node = self.lines[lid]['nodes'][-1]
        start_node = self.lines[lid]['nodes'][0]

        if all_departures is None:
            if self._next_veh_departure[lid] is None:
                new_veh = self.fleet.create_vehicle(start_node,
                                                    capacity=self._veh_capacity,
                                                    activities=[VehicleActivityStop(node=end_node,
                                                                                    path=veh_path)])
                self._next_veh_departure[lid] = (self._current_time_table[lid], new_veh)
                log.info(f"Next departure {new_veh}")
            all_departures = list()

        if time > self._current_time_table[lid]:
            self._current_time_table[lid] = self._next_time_table[lid]
            try:
                self._next_time_table[lid] = next(self._timetable_iter[lid])
            except StopIteration:
                return all_departures
            self.new_departures(time, dt, lid, all_departures)

        next_time = time.add_time(dt)
        if time <= self._current_time_table[lid] < next_time:
            log.info(f"New departure {self._next_veh_departure[lid][1]}")
            start_veh = self._next_veh_departure[lid][1]
            stop_activity = start_veh.activity
            repo_activity = VehicleActivityRepositioning(stop_activity.node,
                                                         stop_activity.path,
                                                         stop_activity.user)
            start_veh.add_activities([repo_activity])
            start_veh.next_activity()

            all_departures.append(start_veh)
            self.vehicles[lid].appendleft(self._next_veh_departure[lid][1])
            self._current_time_table[lid] = self._next_time_table[lid]
            try:
                self._next_time_table[lid] = next(self._timetable_iter[lid])

                new_veh = self.fleet.create_vehicle(start_node,
                                                    capacity=self._veh_capacity,
                                                    activities=[VehicleActivityStop(node=end_node,
                                                                                    path=veh_path)])
                self._next_veh_departure[lid] = (self._next_time_table[lid], new_veh)
                log.info(f"Next departure {new_veh}")
            except StopIteration:
                return all_departures
            self.new_departures(time, dt, lid, all_departures)
        return all_departures

    def add_passenger(self, user: User, drop_node: str, veh: Vehicle, line_nodes: List[str]):
        # self.insert_new_activity(veh, VehicleActivityPickup, veh._current_node, user._current_node, line_nodes, user)
        # self.insert_new_activity(veh, VehicleActivityServing, user._current_node, drop_node, line_nodes, user)
        log.info(f"Add passenger {user} -> {veh}")
        curr_activity = veh.activity
        next_node = curr_activity.node

        take_node_ind = line_nodes.index(user._current_node)
        drop_node_ind = line_nodes.index(drop_node)
        next_node_ind = line_nodes.index(next_node)
        veh_node_ind = line_nodes.index(veh._current_node)

        user.set_state_waiting_vehicle()

        if drop_node_ind <= next_node_ind:
            _insert_in_activity(curr_activity, 0, drop_node, drop_node_ind, take_node_ind, user, veh, veh_node_ind)

        else:
            for ind, curr_activity in enumerate(veh.activities):
                curr_activity = veh.activity
                next_node = curr_activity.node
                if drop_node_ind <= next_node_ind:
                    _insert_in_activity(curr_activity, ind+1, drop_node, drop_node_ind, take_node_ind, user, veh, veh_node_ind)
                    break

    def matching(self, users: Dict[str, Tuple[User, str]]) -> List[str]:
        graph_nodes = self.graph.nodes
        matched_user = []
        for user, drop_node in users.values():
            start = user._current_node

            for lid, line in self.lines.items():
                if start in line['nodes']:
                    user_line = line
                    user_line_id = lid
                    break
            else:
                log.error(f'{user} start is not in the PublicTransport mobility service {self.id}')
                sys.exit(-1)

            if not graph_nodes[start].radj:
                departure_time, waiting_veh = self._next_veh_departure[user_line_id]
                matched_user.append(user.id)
                self.add_passenger(user, drop_node, waiting_veh, user_line["nodes"])
                continue
            else:
                curr_veh = None
                next_veh = None
                it_veh = iter(self.vehicles[user_line_id])
                ind_start = user_line["nodes"].index(start)
                try:
                    curr_veh = next(it_veh)
                    next_veh = next(it_veh)
                except StopIteration:
                    if curr_veh is not None:
                        self.add_passenger(user, drop_node, curr_veh, user_line["nodes"])
                        matched_user.append(user.id)
                        # curr_veh.take_next_user(user, drop_node)
                        continue
                    else:
                        raise VehicleNotFoundError(user, self)

                while True:
                    ind_curr_veh = user_line.stops.index(curr_veh.current_link[1])
                    ind_next_veh = user_line.stops.index(next_veh.current_link[1])
                    if ind_curr_veh <= ind_start < ind_next_veh:
                        # curr_veh.take_next_user(user, drop_node)
                        continue
                    try:
                        curr_veh = next_veh
                        next_veh = next(it_veh)
                    except StopIteration:
                        ind_curr_veh = user_line.stops.index(curr_veh.current_link[1])
                        if ind_curr_veh <= ind_start:
                            # curr_veh.take_next_user(user, drop_node)
                            continue
                        else:
                            log.info(f"{user}, {user._current_node}")
                            log.info(f"{curr_veh.current_link}")
                            raise VehicleNotFoundError(user, self)
        return matched_user

    def step_maintenance(self, dt: Dt):
        for lid in self.lines:
            for new_veh in self.new_departures(self._tcurrent, dt, lid):
                # Mark the Stop state to done to start vehicle journey
                if new_veh.activity.state is VehicleState.STOP:
                    new_veh.activity.is_done = True

                # If no user are waiting for this bus, switch state to repositioning to end of line
                # if not new_veh.activities:
                #     stop_activity = new_veh.activity
                #     repo_activity = VehicleActivityRepositioning(stop_activity.node,
                #                                                  stop_activity.path,
                #                                                  stop_activity.user)
                #     new_veh.add_activities([repo_activity])
                #     new_veh.next_activity()

                log.info(f"Start {new_veh}")
                if self._observer is not None:
                    new_veh.attach(self._observer)

            self.clean_arrived_vehicles(lid)

    def replanning(self):
        pass

    def rebalancing(self, next_demand: List[User], horizon: List[Vehicle]):
        pass

    def service_level_costs(self, nodes: List[str]) -> dict:
        """
        Must return a dict of costs representing the cost of the service computed from a path
        Parameters
        ----------
        path

        Returns
        -------

        """
        return create_service_costs()

    def __dump__(self):
        return {"TYPE": ".".join([PublicTransportMobilityService.__module__, PublicTransportMobilityService.__name__]),
                "ID": self.id}

    @classmethod
    def __load__(cls, data):
        new_obj = cls(data['ID'])
        return new_obj
