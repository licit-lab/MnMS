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

def _to_nodes(path):
    nodes = [l[0][0] for l in path] + [path[-1][0][1]]
    return nodes


def _insert_in_activity(pu_node, ind_pu, do_node, ind_do, user, veh):
    if veh.activity is not None:
        activities_including_curr = [veh.activity] + [a for a in veh.activities]
    else:
        activities_including_curr = [a for a in veh.activities]
    if ind_pu == ind_do:
        # Insertion modifies only one activity in vehicles' activities
        ind = ind_pu
        activity_to_modify = activities_including_curr[ind]
        pu_ind_inpath = _to_nodes(activity_to_modify.path).index(pu_node)
        do_ind_inpath = _to_nodes(activity_to_modify.path).index(do_node)
        if ind == 0:
            # activity_to_modify have begun, pickup activity path should start
            # at vehicle current node
            start_ind_inpath =_to_nodes(activity_to_modify.path).index(veh._current_node)
        else:
            # activity_to_modify has not begun, pickup activity path should start
            # at the beginning of activity_to_modify path
            start_ind_inpath = 0
        # Deduce pickup and serving activities
        pu_path = activity_to_modify.path[start_ind_inpath:pu_ind_inpath]
        do_path = activity_to_modify.path[pu_ind_inpath:do_ind_inpath]
        pu_activity = VehicleActivityPickup(node=pu_node,
                                            path=pu_path,
                                            user=user)
        do_activity = VehicleActivityServing(node=do_node,
                                            path=do_path,
                                            user=user)
        # Modify activity_to_modify
        activity_to_modify.modify_path(activity_to_modify.path[do_ind_inpath:])
        # Insert the new activities and the modified one
        if ind == 0: # TODO: check if veh.activity.state is not VehicleState.STOP condition should be added here
            # Interrupt current activity and insert the new activities plus the
            # modified one
            veh.activity = None
            for a in reversed([pu_activity, do_activity, activity_to_modify]):
                veh.activities.insert(ind, a)
        else:
            # Only insert the new activities, path of activity_to_modify has
            # already been modified
            for a in reversed([pu_activity, do_activity]):
                veh.activities.insert(ind, a)
    else:
        assert ind_pu < ind_do, "Index where pickup activity is going to be inserted in "\
            "vehicle's activities is greater than index where serving activity is going "\
            "to be inserted: this is not consistent."
        # Start by inserting serving activity since it is located after pickup
        activity_to_modify_do = activities_including_curr[ind_do]
        do_ind_inpath = _to_nodes(activity_to_modify_do.path).index(do_node)
        do_path = activity_to_modify_do.path[:do_ind_inpath]
        do_activity = VehicleActivityServing(node=do_node,
                                            path=do_path,
                                            user=user)
        activity_to_modify_do.modify_path(activity_to_modify_do.path[do_ind_inpath:])
        veh.activities.insert(ind_do, do_activity)
        # Then insert pickup activity
        activity_to_modify_pu = activities_including_curr[ind_pu]
        pu_ind_inpath = _to_nodes(activity_to_modify_pu.path).index(pu_node)
        if ind_pu == 0:
            start_ind_inpath =_to_nodes(activity_to_modify_pu.path).index(veh._current_node)
        else:
            start_ind_inpath = 0
        pu_path = activity_to_modify_pu.path[start_ind_inpath:pu_ind_inpath]
        pu_activity = VehicleActivityPickup(node=pu_node,
                                            path=pu_path,
                                            user=user)
        activity_to_modify_pu.modify_path(activity_to_modify_pu.path[pu_ind_inpath:])
        if ind_pu == 0: # TODO: check if veh.activity.state is not VehicleState.STOP condition should be added here
            # Interrupt current activity and insert the pickup activity plus the
            # modified one
            veh.activity = None
            for a in reversed([pu_activity, activity_to_modify_pu]):
                veh.activities.insert(ind_pu, a)
        else:
            # Only insert the pickup activity, path of activity_to_modify_pu has
            # already been modified
            veh.activities.insert(ind_pu, pu_activity)


class PublicTransportMobilityService(AbstractMobilityService):
    def __init__(self, _id: str, veh_capacity=50):
        """
        Implement a public transport mobility service, it can create lines

        Args:
            _id: The id of the service
            veh_capacity: The capacity of the vehicle using this service
        """
        super(PublicTransportMobilityService, self).__init__(_id, veh_capacity=veh_capacity, dt_matching=0,
                                                             dt_periodic_maintenance=0)
        self.vehicles: Dict[str, Deque[Vehicle]] = defaultdict(deque)
        self._timetable_iter: Dict[str, Generator[Time, None, None]] = dict()
        self._current_time_table: Dict[str, Time] = dict()
        self._next_time_table: Dict[str, Time] = dict()
        self._next_veh_departure: Dict[str, Optional[Tuple[Time, Vehicle]]] = defaultdict(lambda: None)

        self.gnodes = None
        self._cache_request_vehicles = dict()

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
                new_veh._current_link = veh_path[0][0]
                new_veh._remaining_link_length = veh_path[0][1]
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
                new_veh._current_link = veh_path[0][0]
                new_veh._remaining_link_length = veh_path[0][1]
                self._next_veh_departure[lid] = (self._next_time_table[lid], new_veh)
                log.info(f"Next departure {new_veh}")
            except StopIteration:
                return all_departures
            self.new_departures(time, dt, lid, all_departures)
        return all_departures

    def add_passenger(self, user: User, drop_node: str, veh: Vehicle, line_nodes: List[str]):
        log.info(f"Add passenger {user} -> {veh}")
        user.set_state_waiting_vehicle()

        pu_node_ind = line_nodes.index(user._current_node)
        do_node_ind = line_nodes.index(drop_node)
        assert pu_node_ind < do_node_ind, 'Pickup should necessarily take place '\
            'before dropoff on the public transport line.'

        # Get the indexes of veh.activities where pickup and serving activities
        # should be inserted
        if veh.activity is not None:
            activities_including_curr = [veh.activity] + [a for a in veh.activities]
        else:
            activities_including_curr = [a for a in veh.activities]
        ind_pu = -1
        for ind, activity in enumerate(activities_including_curr):
            activity_node = activity.node
            activity_node_ind = line_nodes.index(activity_node)
            if pu_node_ind <= activity_node_ind and ind_pu == -1:
                ind_pu = ind
            if do_node_ind <= activity_node_ind:
                ind_do = ind
                break # if we found dropoff we necessarily have found pickup before

        # Insert the activities corresponding to pickup and serving in vehciles' activities
        _insert_in_activity(user._current_node, ind_pu, drop_node, ind_do, user, veh)

    def estimation_pickup_time(self, user: User, veh: Vehicle, line: dict):
        user_node = user._current_node
        veh_node = veh._current_node
        veh_link_borders = veh.current_link
        veh_link_length = self.gnodes[veh_link_borders[0]].adj[veh_link_borders[1]].length
        veh_remaining_length = veh.remaining_link_length
        veh_traveled_dist_link = veh_link_length - veh_remaining_length

        line_stops = line["nodes"]
        ind_user = line_stops.index(user_node)
        ind_veh = line_stops.index(veh_node)

        path = line_stops[ind_veh:ind_user+1]
        dist = 0
        for i in range(len(path)-1):
            dist += self.gnodes[path[i]].adj[path[i+1]].length
        dist -= veh_traveled_dist_link

        dt = Dt(seconds=dist/veh.speed)

        return dt

    def request(self, users: Dict[str, Tuple[User, str]]) -> Dict[str, Dt]:
        matched_user = dict()
        for user, drop_node in users.values():
            start = user._current_node

            # Select the proper line for user
            for lid, line in self.lines.items():
                if start in line['nodes']:
                    user_line = line
                    user_line_id = lid
                    break
            else:
                log.error(f'{user} start is not in the PublicTransport mobility service {self.id}')
                sys.exit(-1)

            if not self.gnodes[start].radj:
                departure_time, waiting_veh = self._next_veh_departure[user_line_id]
                matched_user[user.id] = (waiting_veh, user_line)
                # self.add_passenger(user, drop_node, waiting_veh, user_line["nodes"])
                continue
            else:
                ind_start = user_line["nodes"].index(start)
                for veh in reversed(list(self.vehicles[user_line_id])):
                    ind_curr_veh = user_line["nodes"].index(veh.current_link[1])
                    if ind_curr_veh <= ind_start:
                        matched_user[user.id] = (veh, user_line)
                        break
                else:
                    log.warning(f"No vehicle found for {user}")


                # curr_veh = None
                # next_veh = None
                # it_veh = iter(self.vehicles[user_line_id])
                # ind_start = user_line["nodes"].index(start)
                # try:
                #     curr_veh = next(it_veh)
                #     next_veh = next(it_veh)
                # except StopIteration:
                #     if curr_veh is not None:
                #         matched_user[user.id] = (curr_veh, user_line)
                #         # self.add_passenger(user, drop_node, curr_veh, user_line["nodes"])
                #         # curr_veh.take_next_user(user, drop_node)
                #         continue
                #     else:
                #         raise VehicleNotFoundError(user, self)
                #
                # while True:
                #     ind_curr_veh = user_line["nodes"].index(curr_veh.current_link[1])
                #     ind_next_veh = user_line["nodes"].index(next_veh.current_link[1])
                #     if ind_curr_veh <= ind_start < ind_next_veh:
                #         # curr_veh.take_next_user(user, drop_node)
                #         matched_user[user.id] = (curr_veh, user_line)
                #         print(f"What should I do there?")
                #         break
                #     try:
                #         curr_veh = next_veh
                #         next_veh = next(it_veh)
                #     except StopIteration:
                #         ind_curr_veh = user_line["nodes"].index(curr_veh.current_link[1])
                #         if ind_curr_veh <= ind_start:
                #             # curr_veh.take_next_user(user, drop_node)
                #             continue
                #         else:
                #             log.info(f"{user}, {user._current_node}")
                #             log.info(f"{curr_veh.current_link}")
                #             raise VehicleNotFoundError(user, self)

        estimation_pickup = {u: self.estimation_pickup_time(users[u][0], veh, line) for u, (veh, line) in matched_user.items()}
        self._cache_request_vehicles = matched_user

        return estimation_pickup

    def matching(self, user: User, drop_node: str):
        veh, line = self._cache_request_vehicles[user.id]
        self.add_passenger(user, drop_node, veh, line["nodes"])

    def step_maintenance(self, dt: Dt):
        self._cache_request_vehicles = dict()
        self.gnodes = self.graph.nodes
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
