from collections import defaultdict
from copy import copy, deepcopy
from enum import Enum
from typing import Union, List, Tuple, Optional, Dict

from mnms.time import Time, Dt
from mnms.tools.observer import TimeDependentSubject
from mnms.log import create_logger
from mnms.tools.dict_tools import sum_dict

import numpy as np
from numpy.linalg import norm as _norm

log = create_logger(__name__)

def find_sublist_in_list(sl,l):
    results=[]
    sll=len(sl)
    for ind in (i for i,e in enumerate(l) if e==sl[0]):
        if l[ind:ind+sll]==sl:
            results.append((ind,ind+sll-1))
    return results

class UserState(Enum):
    ARRIVED = 0
    WAITING_ANSWER = 1
    WAITING_VEHICLE = 2
    WALKING = 3
    INSIDE_VEHICLE = 4
    STOP = 5
    DEADEND = 6


class User(TimeDependentSubject):
    default_response_dt = Dt(minutes=2)
    default_pickup_dt = Dt(minutes=5)

    def __init__(self,
                 id: str,
                 origin: Union[str, Union[np.ndarray, List]],
                 destination: Union[str, Union[np.ndarray, List]],
                 departure_time: Time,
                 available_mobility_services=None,
                 mobility_services_graph: str=None,
                 path: Optional["Path"] = None,
                 response_dt: Optional[Dt] = None,
                 pickup_dt: Optional[Dt] = None,
                 forced_path_chosen_mobility_services: Optional[Dict[str,str]] = None):
        """
        Class representing a User in the simulation.

        Args:
            -id: The unique id of the User
            -origin: The origin of the User
            -destination: the destination of the User
            -departure_time: The departure time
            -available_mobility_services: The available mobility services
            -mobility_services_graph: Id of the mobility services graph
                                        to use for this traveler
            -path: The path of the User
            -response_dt: The maximum dt a User is ok to wait from a mobility service
            -pickup_dt: The maximum dt a User is ok to wait for a pick up
            -forced_path_chosen_mobility_services: Dict with layers ids as keys and chosen
             mobility services id on each layer as values, it is used when one want to
             force the initial path of a user with the CSVDemandManager
        """
        super(User, self).__init__()
        self.id = id
        self.origin = origin if not isinstance(origin, list) else np.array(origin)
        self.destination = destination if not isinstance(destination, list) else np.array(destination)
        self.departure_time = departure_time
        self.arrival_time = None
        self.available_mobility_services = available_mobility_services if available_mobility_services is None else set(available_mobility_services)
        self.mobility_services_graph = mobility_services_graph
        self.response_dt = User.default_response_dt.copy() if response_dt is None else response_dt
        self.pickup_dt = defaultdict(lambda: User.default_pickup_dt.copy()) if pickup_dt is None else defaultdict(lambda: pickup_dt)

        self.parameters: Dict = dict()

        self._current_node = None
        self._current_link = None
        self._remaining_link_length = None
        self._position = None
        self._achieved_path = list()
        self._achieved_path_ms = list()
        self._vehicle = None
        self._waited_vehicle = None
        self._requested_service = None
        self._parked_personal_vehicles = dict()
        self._personal_vehicles = dict()
        self._distance = 0
        self._interrupted_path = None
        self._state = UserState.STOP
        self._deadend_at_next_node = False

        if path is None:
            self.path: Optional[Path] = None
            self.forced_path_chosen_mobility_services = None
        else:
            self.set_path(path)
            self.forced_path_chosen_mobility_services = forced_path_chosen_mobility_services

    def __repr__(self):
        return f"User('{self.id}', {self.origin}->{self.destination}, {self.departure_time})"

    @property
    def current_node(self):
        return self._current_node

    @current_node.setter
    def current_node(self, n):
        self._current_node = n

    @property
    def current_link(self):
        return self._current_link

    @current_link.setter
    def current_link(self, l : Tuple[str,str]):
        self._current_link = l

    @property
    def remaining_link_length(self):
        return self._remaining_link_length

    @remaining_link_length.setter
    def remaining_link_length(self, l: float):
        self._remaining_link_length = l

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, pos):
        self._position = pos

    @property
    def achieved_path(self):
        return self._achieved_path

    @achieved_path.setter
    def achieved_path(self, ap: List[str]):
        self._achieved_path = ap

    @property
    def achieved_path_ms(self):
        return self._achieved_path_ms

    @achieved_path_ms.setter
    def achieved_path_ms(self, ap_ms: List[str]):
        self._achieved_path_ms = ap_ms

    @property
    def vehicle(self):
        return self._vehicle

    @vehicle.setter
    def vehicle(self, veh: "Vehicle"):
        self._vehicle = veh

    @property
    def waited_vehicle(self):
        return self._waited_vehicle

    @waited_vehicle.setter
    def waited_vehicle(self, veh: "Vehicle"):
        self._waited_vehicle = veh

    @property
    def requested_service(self):
        return self._requested_service

    @requested_service.setter
    def requested_service(self, s: "AbstractMobilityService"):
        self._requested_service = s

    @property
    def parked_personal_vehicles(self):
        return self._parked_personal_vehicles

    @property
    def personal_vehicles(self):
        return self._personal_vehicles

    @property
    def distance(self):
        return self._distance

    @property
    def interrupted_path(self):
        return self._interrupted_path

    @interrupted_path.setter
    def interrupted_path(self, p: "Path"):
        self._interrupted_path = p

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, s: "UserState"):
        self._state = s

    @property
    def deadend_at_next_node(self):
        return self._deadend_at_next_node

    @deadend_at_next_node.setter
    def deadend_at_next_node(self, b):
        self._deadend_at_next_node = b

    @property
    def is_in_vehicle(self):
        return self.vehicle is not None

    @property
    def max_detour_ratio(self):
        assert 'max_detour_ratio' in self.parameters.keys()
        return self.parameters['max_detour_ratio']

    def get_current_node_index(self, path_nodes=None):
        """Method that returns the index of user's current node within a path.
        This method manages the case when user's path passes several times through
        the same node. It can happen when user replans.

        Returns:
            -cnode_ind: index of user's current node in her path, -1 if user's current
                        node is not present in user's path
            -path_nodes: path in which user's current node should be found, if not specified,
                   it is searched in user's current path
        """
        path_nodes = path_nodes if path_nodes is not None else self.path.nodes
        cnode_ind = list(np.where(np.array(path_nodes) == self.current_node)[0])
        if len(cnode_ind) == 0:
            return -1
        if len(cnode_ind) == 1:
            cnode_ind = cnode_ind[0]
        else:
            c = self.achieved_path.count(self.current_node)
            if c == 0:
                cnode_ind = cnode_ind[0]
            else:
                cnode_ind = cnode_ind[c-1]
        return cnode_ind

    def get_node_index_in_path(self, node: str, last_achieved: bool = False) -> int:
        """Method that finds the index of a node in user's path considering the path
        already achieved. The index of node returned should not be already passed by user.

        Args:
            -node: the node to find the index of
            -last_achieved: if True the index to find is the last achieved node,
             if False it is the next to be achieved

        Returns:
            -ind: the index of the node in user's path, -1 if node has not been found
        """
        node_inds = list(np.where(np.array(self.path.nodes) == node)[0])
        if len(node_inds) == 0:
            return -1
        if len(node_inds) == 1:
            ind = node_inds[0]
        else:
            c = self.achieved_path.count(node)
            if c == 0:
                ind = node_inds[0]
            else:
                if last_achieved:
                    ind = node_inds[c-1]
                else:
                    ind = node_inds[c]
        return ind

    def get_mobility_service_index_in_path(self, ms_id: str) -> int:
        """Method that finds the index of a mobility service in user's path considering
        the path already achieved.

        Args:
            -ms_id: id of the mobility service to find in user's path

        Returns:
            -ind: index of the mobility service, -1 if it has not been found
        """
        ms_inds = list(np.where(np.array(self.path.mobility_services) == ms_id)[0])
        if len(ms_inds) == 0:
            ind = -1
        elif len(ms_inds) == 1:
            ind = ms_inds[0]
        else:
            c = self.achieved_path_ms.count(ms_id)
            if c == 0:
                ind = ms_inds[0]
            else:
                ind = ms_inds[c]
        return ind

    def finish_trip(self, arrival_time:Time):
        """Method that updates user's attributes when she arrives at her final destination.

        Args:
            -arrival_time: time at which user arrived
        """
        self.arrival_time = arrival_time
        self.set_state_arrived()
        log.info(f"User {self.id} arrived at destination at {arrival_time}")
        self.notify(arrival_time)

    def set_pickup_dt(self, ms, dt):
        self.pickup_dt[ms] = dt

    def set_available_mobility_services(self, ams):
        self.available_mobility_services = ams
        log.info(f'User {self.id} updated list of available mobility services to {self.available_mobility_services}')

    def remove_available_mobility_service(self, ms):
        self.available_mobility_services.remove(ms)
        log.info(f'User {self.id} updated list of available mobility services to {self.available_mobility_services}')

    def cancel_match(self, mlgraph, cost):
        """Method that cancels user's current match by removing user's pickup and
        serving activites from waited vehicle's plan.

        Args:
            -mlgraph: multilayergraph
            -cost: name of the cost user considers

        Returns:

        """
        # Remove user pickup and serving activity from waited vehicle's plan
        veh = self.waited_vehicle
        assert veh is not None and self.state == UserState.WAITING_VEHICLE, f'Wrong call of cancel_match method...'
        veh_ms = veh.mobility_service
        veh_ms_obj = [ms for ms in mlgraph.get_all_mobility_services() if ms.id == veh_ms][0]
        if type(veh_ms_obj).__name__ == 'PublicTransportMobilityService':
            veh_ms_obj.remove_user_activities(self)
        else:
            veh_ms_obj.remove_user_activities(self, mlgraph, cost)

    def modify_part_of_path(self, old_part, new_part, gnodes, mlgraph, cost):
        """Method that modifies a part of user's path.
        NB: used after vehicle reroute due to banning, the mobility services do
            not change

        Args:
            -old_part: the old pat of user's path to override
            -new_part: the new part of user's path replacing the old one
            -gnodes: the multi layer graph nodes
            -mlgraph: the multi layer graph
        """
        # Find old part in user's path
        st_end_indices = find_sublist_in_list(old_part, self.path.nodes)
        if len(st_end_indices) != 1:
            log.error(f'Cannot find or found several times old part {old_part} of user {self.id} path {self.path.nodes}...')
            sys.exit(-1)
        # Override this old part
        start_idx, end_idx = st_end_indices[0]
        new_path_nodes = self.path.nodes[:start_idx] + new_part + self.path.nodes[end_idx+1:]
        new_path = Path(None, new_path_nodes)
        new_path.construct_layers_from_links(gnodes)
        new_path.set_mobility_services(self.path.mobility_services) # Hyp = mobility services do not change
        new_path.update_path_cost(mlgraph, cost)
        service_costs = sum_dict(*(mlgraph.layers[layer].mobility_services[service].service_level_costs(new_path.nodes[node_inds]) \
            for (layer, node_inds), service in zip(new_path.layers, new_path.mobility_services) if service != 'WALK'))
        new_path.service_costs = service_costs
        # Set user's new path
        self.path = new_path

    def modify_path_leg(self, ms_id: str, new_nodes: list[str]):
        """Method that modifies the nodes of one leg of user's path.

        Args:
            -ms_id: the id of the mobility service used on the leg to modify
            -new_nodes: the new list of nodes for the leg
        """
        ## Find the leg concerned
        modif = False
        for i, (ms, (layer, sl)) in enumerate(zip(self.path.mobility_services, self.path.layers)):
            if ms == ms_id and self.path.nodes[sl][-1] == new_nodes[-1]:
                # Update nodes and slice of the leg
                start_ind = sl.start
                mid_ind = self.get_node_index_in_path(new_nodes[0], last_achieved=True)
                stop_ind = sl.start + (mid_ind-start_ind) + len(new_nodes)
                del self.path.nodes[mid_ind:sl.stop]
                for n in reversed(new_nodes):
                    self.path.nodes.insert(mid_ind, n)
                self.path.layers[i] = (layer, slice(start_ind, stop_ind, 1))
                modif = True
            elif modif:
                next_stop_ind = stop_ind-1 + (sl.stop - sl.start)
                self.path.layers[i] = (layer, slice(stop_ind-1, next_stop_ind, 1))
                stop_ind = next_stop_ind
        if modif == False:
            log.warning(f'Could not find the {ms_id} leg to modify in user path {self.path}...')
        else:
            ##TODO: Update path cost if it is used somehow after path leg modification because of ridesharing detour
            pass

    def update_path(self, path: "Path", gnodes, mlgraph, cost: str, max_teleport_dist: float = None):
        """Method that updates the path of user.

        Args:
            -path: path that should starts with a node belonging to user's current path
                   that has not already been passed by the user. This path will replace
                   all the nodes located after this common node in user's current path.
            -gnodes: multilayergraph nodes
            -mlgraph: multilayergraph
            -cost: name of the cost user considers
            -max_teleport_dist: maximal distance on which teleportation is authorized, if
                                None, it means that teleportation is not authorized

        Returns:
            -new_drop_node: if user is inside a vehicle, designates the new node where
                            this vehicle should drop off user
                            if user is waiting a vehicle, designates the new node the
                            waited vehicle should drop off user, current node if user
                            does not plan to ride this vehicle anymore
        """
        # Small check on new path consistency
        current_node_ind = self.get_current_node_index()
        path_first_node_ind = self.get_node_index_in_path(path.nodes[0])
        teleported = False
        if path_first_node_ind == -1 or path_first_node_ind < current_node_ind:
            if max_teleport_dist is None:
                log.error(f'User {self.id} tried to update path with current node index = {current_node_ind} '\
                    f'and new path first node index = {path_first_node_ind} without the possibility to teleport.')
                sys.exit(-1)
            else:
                # Teleport if required
                path_first_node = gnodes[path.nodes[0]]
                teleported = self.teleport(self.position, path_first_node, max_teleport_dist, gnodes)

        if teleported:
            # Replace path and launch user on this new path
            new_path = path
            new_drop_node = None
        else:
            # Build user's new path
            new_path_nodes = self.path.nodes[:path_first_node_ind] + path.nodes
            new_path = Path(None, new_path_nodes)
            new_path.construct_layers_from_links(gnodes)
            new_mobservices_indices = [i for i,(lid,sl) in enumerate(self.path.layers) if \
                path_first_node_ind >= sl.stop or (path_first_node_ind > sl.start and path_first_node_ind < sl.stop)]
            new_mobservices = [self.path.mobility_services[i] for i in new_mobservices_indices]
            if self.state == UserState.INSIDE_VEHICLE:
                if new_mobservices[-1] == path.mobility_services[0]:
                    new_mobservices.extend(path.mobility_services[1:])
                    current_layer = [(lid,sl) for lid,sl in new_path.layers if current_node_ind >= sl.start and path_first_node_ind < sl.stop][0]
                    new_drop_node = new_path_nodes[current_layer[1].stop-1]
                else:
                    new_mobservices.extend(path.mobility_services)
                    new_drop_node = path.nodes[0]
            elif self.state == UserState.WAITING_VEHICLE:
                if new_mobservices[-1] == path.mobility_services[0]:
                    new_mobservices.extend(path.mobility_services[1:])
                else:
                    new_mobservices.extend(path.mobility_services)
                if self.waited_vehicle.mobility_service == path.mobility_services[0]:
                    # User maintains her match
                    new_drop_node = path.nodes[path.layers[0][1].stop-1]
                else:
                    # User wont ride the waited vehicle
                    new_drop_node = self.current_node
            elif self.state == UserState.WAITING_ANSWER:
                if new_mobservices[-1] == path.mobility_services[0]:
                    new_mobservices.extend(path.mobility_services[1:])
                else:
                    new_mobservices.extend(path.mobility_services)
                if self.requested_service.id == path.mobility_services[0]:
                    # User maintains her request, eventually update requested drop node
                    new_drop_node = path.nodes[path.layers[0][1].stop-1]
                else:
                    # User wont ride the waited vehicle
                    new_drop_node = self.current_node
            elif self.state == UserState.WALKING:
                if new_mobservices[-1] == path.mobility_services[0]:
                    new_mobservices.extend(path.mobility_services[1:])
                else:
                    new_mobservices.extend(path.mobility_services)
                new_drop_node = None
            else:
                log.error(f'Case not yet developped update_path with {self.state} user')
                sys.exit(-1)
            new_path.set_mobility_services(new_mobservices)
            new_path.update_path_cost(mlgraph, cost)
            service_costs = sum_dict(*(mlgraph.layers[layer].mobility_services[service].service_level_costs(new_path.nodes[node_inds]) \
                for (layer, node_inds), service in zip(new_path.layers, new_path.mobility_services) if service != 'WALK'))
            new_path.service_costs = service_costs

        # Set user's new path
        self.path = new_path

        # Return the new drop node of user for the vehicle she currently is inside
        return new_drop_node

    def update_path_and_requested_service_buffer(self, path: "Path", gnodes, mlgraph, cost: str, max_teleport_dist: float):
        """Method that updates the path of a user who is currently waiting an answer from
        a mobility service and updates the corresponding request consequently.

        Args:
            -path: new path, it should starts with a node belonging to user's current path
                   that has not already been passed by the user. This path will replace
                   all the nodes located after this common node in user's current path.
            -gnodes: multilayergraph nodes
            -mlgraph: multilayergraph
            -cost: name of the cost user considers
            -max_teleport_dist: maximal distance on which teleportation is authorized
        """
        ### Update path
        new_drop_node = self.update_path(path, gnodes, mlgraph, cost, max_teleport_dist=max_teleport_dist)

        if new_drop_node == self.current_node or new_drop_node is None:
            # User will not take the service she is waiting answer from, remove user request from service's buffer
            self.requested_service.cancel_request(self.id)
            self.set_state_stop()
            current_node_ind = self.get_current_node_index()
            self.current_link = (self.path.nodes[current_node_ind],self.path.nodes[current_node_ind+1])
            self.remaining_link_length = gnodes[self.path.nodes[current_node_ind]].adj[self.path.nodes[current_node_ind+1]].length
        else:
            # Find user former requested drop node
            former_drop_node = self.requested_service.user_buffer[self.id].drop_node
            if new_drop_node != former_drop_node:
                # User maintains her request but changes the requested drop node
                self.requested_service.update_request(self, new_drop_node)
            else:
                # User will maintain her request with the same drop node, there is nothing to do
                pass

    def update_path_and_waited_vehicle_plan(self, path: "Path", gnodes, mlgraph, cost: str, max_teleport_dist: float):
        """Method that updates the path of a user who is currently waiting a vehicle and
        the waited vehicle plan consequently.

        Args:
            -path: new path, it should starts with a node belonging to user's current path
                   that has not already been passed by the user. This path will replace
                   all the nodes located after this common node in user's current path.
            -gnodes: multilayergraph nodes
            -mlgraph: multilayergraph
            -cost: name of the cost user considers
            -max_teleport_dist: maximal distance on which teleportation is authorized
        """
        ### Update path
        new_drop_node = self.update_path(path, gnodes, mlgraph, cost, max_teleport_dist=max_teleport_dist)

        ### Update vehicle's plan consequently
        veh = self.waited_vehicle
        veh_ms = veh.mobility_service
        veh_ms_obj = [ms for ms in mlgraph.get_all_mobility_services() if ms.id == veh_ms][0]

        if new_drop_node == self.current_node or new_drop_node is None:
            # User will not take the vehicle she was waiting for, remove user pickup and
            # serving activity from vehicle's plan
            self.cancel_match(mlgraph, cost)
            self.set_state_stop()
            current_node_ind = self.get_current_node_index()
            self.current_link = (self.path.nodes[current_node_ind],self.path.nodes[current_node_ind+1])
            self.remaining_link_length = gnodes[self.path.nodes[current_node_ind]].adj[self.path.nodes[current_node_ind+1]].length
        else:
            # Find user serving activity in the waited vehicle's plan and former drop node
            all_activities = [self.waited_vehicle.activity] + list(self.waited_vehicle.activities)
            u_serving_act_ind = [i for i in range(len(all_activities)) if all_activities[i].user == self and type(all_activities[i]).__name__=='VehicleActivityServing'][0]
            former_drop_node = all_activities[u_serving_act_ind].node
            if new_drop_node != former_drop_node:
                # User will ride the vehicle she is waiting for but changes drop node
                # For public transportation vehicles, we keep the order in which stops are visited,
                # not necessarily the order in which activities are ordered
                if type(veh_ms_obj).__name__ == 'PublicTransportMobilityService':
                    veh_ms_obj.modify_user_drop_node(self, veh, new_drop_node, former_drop_node)
                # For other types of vehicles, we keep the order in which activities are ordered
                else:
                    veh_ms_obj.modify_user_drop_node(self, veh, new_drop_node, former_drop_node, gnodes, mlgraph, cost)
            else:
                # User will use the vehicle she is waiting for and do not change drop node,
                # there is nothing to do
                pass

    def update_path_and_current_vehicle_plan(self, path: "Path", gnodes, mlgraph, cost: str):
        """Method that updates the path of a user who is currently inside a vehicle.

        Args:
            -path: new path, it should starts with a node belonging to user's current path
                   that has not already been passed by the user. This path will replace
                   all the nodes located after this common node in user's current path.
            -gnodes: multilayergraph nodes
            -mlgraph: multilayergraph
            -cost: name of the cost user considers
        """
        ### Update path
        new_drop_node = self.update_path(path, gnodes, mlgraph, cost)

        ### Update vehicle's plan consequently
        self.modify_current_ride_drop_node(new_drop_node, gnodes, mlgraph, cost)

    def modify_current_ride_drop_node(self, new_drop_node, gnodes, mlgraph, cost):
        """Method that update the drop node of user in current vehicle's plan.

        Args:
            -new_drop_node: new drop node for the current ride
            -gnodes: multilayergraph nodes
            -mlgraph: multilayergraph
            -cost: name of the cost user considers
        """
        assert self.vehicle is not None, 'Wrong call of modify_current_ride_drop_node method; user should be inside a vehicle...'

        # Find user serving activity in current vehicle's plan and former drop node
        all_activities = [self.vehicle.activity] + list(self.vehicle.activities)
        u_serving_act_ind = [i for i in range(len(all_activities)) if all_activities[i].user == self][0] # pickup activity already done because user is in the veh
        former_drop_node = all_activities[u_serving_act_ind].node

        # Update vehicle's plan if required
        if new_drop_node != former_drop_node:
            # Differentiate update plan of public transport and non public transport vehicles
            veh_ms = self.vehicle.mobility_service
            veh_ms_obj = [ms for ms in mlgraph.get_all_mobility_services() if ms.id == veh_ms][0]
            # 1. For public transportation vehicles, we keep the order in which stops are visited,
            #    not necessarily the order in which activities are ordered
            if type(veh_ms_obj).__name__ == 'PublicTransportMobilityService':
                veh_ms_obj.modify_passenger_drop_node(self, new_drop_node, former_drop_node)
            # 2. For other types of vehicles, we keep the order in which activities are ordered
            else:
                veh_ms_obj.modify_passenger_drop_node(self, new_drop_node, former_drop_node, gnodes, mlgraph, cost)

    def set_path(self, path: "Path", gnodes = None, max_teleport_dist: float = 0., teleport_origin = None):
        """Method that set user's path and checks the conditions of eventual teleporting.

        Args:
            -path: user's new path
            -gnodes: multilayer graph nodes
            -max_teleport_dist: the maximum distance authorized for teleporting
            -teleport_origin: the origin of eventual teleporting
        """
        if gnodes is not None and teleport_origin is not None:
            teleported = self.teleport(teleport_origin, gnodes[path.nodes[0]], max_teleport_dist, gnodes)
            if teleported:
                self.set_state_stop()
        self.path: Path = path
        self.current_node = path.nodes[0]
        self.current_link = (path.nodes[0], path.nodes[1])

    def start_path(self, gnodes):
        self.remaining_link_length = gnodes[self.path.nodes[0]].adj[self.path.nodes[1]].length

    def interrupt_path(self, tcurrent: Time):
        """Method that interrupts user's current path.

        Args:
            -tcurrent: time at which user stopped to follow her path
        """
        self.set_state_stop()
        self.interrupted_path = copy(self.path)
        self.path = None
        self.notify(tcurrent)

    def teleport(self, teleport_origin, dnode, max_teleport_dist, gnodes):
        """Method that checks the conditions for user teleportation and proceeds
        to the teleportation if they are met.

        Args:
            -teleport_origin: position from where user teleports
            -dnode: destination node of the teleportation
            -max_teleport_dist: maximal distance authorized for a teleportation
            -gnodes: multilayer graph nodes

        Returns:
            -teleported: bool specifying if user got teleported or not
        """
        teleported = False
        dist = _norm(np.array(teleport_origin) - np.array(dnode.position))
        if dist <= max_teleport_dist and (dist > 0 or self.current_node != dnode.id or self.position != dnode.position):
            log.warning(f'User {self.id} teleport from {self.current_node} ({teleport_origin}) to {dnode.id} ({dnode.position}) for {dist} meters')
            teleported = True
        elif dist > max_teleport_dist and dist > 0:
            log.error(f'User {self.id} tried to teleport from {self.current_node} to {dnode.id} for {dist} meters: it is prohibited ! ')
            sys.exit(-1)

        if teleported:
            self.current_node = dnode.id
            self.position = dnode.position
            self.achieved_path = [dnode.id] # after teleportation, achieved_path is
                                            # reset and path does not contain the route
                                            # user has already passed through
            self.achieved_path_ms = []
        return teleported

    def set_position(self, current_link:Tuple[str, str], current_node:str, remaining_length:float, position:np.ndarray, tcurrent: Time):
        """Method that updates user's position (including current node, link,
        remaining link length, position and achieved path).

        Args:
            -current_link: user's new current link
            -current_node: user's new current node
            -remaining_length: remaining length to travel on current link
            -position: coordinates of user's new position
            -tcurrent: current time
        """
        self.current_node = current_node
        self.current_link = current_link
        self.remaining_link_length = remaining_length
        self.position = position
        self.update_achieved_path(current_node)
        if self.deadend_at_next_node:
            self.set_state_deadend(tcurrent)

    def update_achieved_path(self, reached_node):
        """Method that updates user's achieved path with the new reached node.

        Args:
            -reached_node: node user has just reached
        """
        if len(self.achieved_path) == 0:
            self.achieved_path.append(self.current_node)
        if reached_node != self.achieved_path[-1]:
            self.achieved_path.append(reached_node)

    def update_achieved_path_ms(self, ms_id):
        """Method that updates user's achieved path mobility services with a new
        service user has just left.

        Args:
            -ms_id: the id of the mobility service user has just left
        """
        self.achieved_path_ms.append(ms_id)

    def update_distance(self, dist: float):
        """Method that increments the distance traveled by user.

        Args:
            -dist: the distance to add
        """
        self._distance += dist

    def set_state_arrived(self):
        self.state = UserState.ARRIVED

    def set_state_walking(self):
        self.state = UserState.WALKING

    def set_state_inside_vehicle(self):
        self.state = UserState.INSIDE_VEHICLE

    def set_state_waiting_vehicle(self, veh):
        """Method that updates the user state into WAITING_VEHICLE and identifies
        the vehicle user is waiting for.

        Args:
            -veh: the vehicle user is waiting for
        """
        self.state = UserState.WAITING_VEHICLE
        self.waited_vehicle = veh

    def set_state_waiting_answer(self):
        self.state = UserState.WAITING_ANSWER

    def set_state_stop(self):
        self.state = UserState.STOP

    def set_state_deadend(self, tcurrent: Time):
        self.state = UserState.DEADEND
        self.vehicle = None
        self.waited_vehicle = None
        self.requested_service = None
        self.path = None
        self.notify(tcurrent)

    def get_failed_mobility_service(self):
        """Method that finds the mobility service for which user undergone a match
        failure. It should be called when user has interrupted her path because she got
        refused.

        Args:

        Returns:
            -failed_mservice: the mobility service that refused used
        """
        assert ((self.interrupted_path is not None) and (self.current_node is not None)), \
            f'Cannot find back the mobility service for which user {self.id} undergone a match failure'
        upath = self.interrupted_path.nodes
        ind_current_node = self.get_current_node_index(upath)
        for ilayer, (layer, slice_nodes) in enumerate(self.interrupted_path.layers):
            if slice_nodes.start == ind_current_node:
                failed_mservice = self.interrupted_path.mobility_services[ilayer]
                return failed_mservice
        log.error(f'Could not find back the mobility service for which user {self.id} undergone a match failure')
        sys.exit(-1)

    def add_personal_vehicle(self, mid, veh):
        """Method to add a personal vehicle to this user.

        Args:
            -mid: mobility service id the vehicle belongs to
            -veh: the personal vehicle of this user
        """
        assert mid not in self.personal_vehicles, f'Try to add a personal vehicle '\
            f'for user {self.id} and service {mid} but one already exists...'
        self._personal_vehicles[mid] = veh

    def park_personal_vehicle(self, ms, node):
        """Method that registers the mobility service and the parking location of user's
        personal vehicle.

        Args:
            -ms: name of the mobility service with which is associated the parked vehicle
            -node: location where the personal vehicle is parked
        """
        self._parked_personal_vehicles[ms] = node


class Path(object):
    def __init__(self, cost: float=None, nodes: Union[List[str], Tuple[str]] = None):
        """
        Path object describing a User path in the simulation
        Parameters
        ----------
        cost: The cost of the path
        nodes: The nodes describing the path
        """
        self.path_cost: float = cost
        self.nodes: Tuple[str] = nodes

        self.layers: List[Tuple[str, slice]] = list()
        self.mobility_services = list()
        self.service_costs = dict()

    def set_mobility_services(self, ms):
        self.mobility_services = ms

    def construct_layers_from_links(self, gnodes):
        previous_layer = gnodes[self.nodes[0]].adj[self.nodes[1]].label
        index = 0
        i = 0
        layers = []
        for i in range(1,len(self.nodes)-1):
            layer = gnodes[self.nodes[i]].adj[self.nodes[i+1]].label
            if layer != previous_layer:
                layers.append((previous_layer, slice(index,i+1,1)))
                index = i
                previous_layer = layer
        layers.append((previous_layer, slice(index, i+2,1)))
        self.layers = layers

    def construct_layers(self, gnodes):
        layer = gnodes[self.nodes[1]].label
        start = 1
        nodes_number = len(self.nodes)
        for i in range(2, nodes_number-1):
            ilayer = gnodes[self.nodes[i]].label
            linklayer = gnodes[self.nodes[i-1]].adj[self.nodes[i]].label
            # If we change layer or we temporary leave the layer to re-enter it
            # with a transit link, this is the case when user transfer from one
            # bus line to another bus line belonging to the same layer for example
            if ilayer != layer or linklayer == 'TRANSIT':
                self.layers.append((layer, slice(start, i, 1)))
                layer = ilayer
                start = i
        self.layers.append((layer, slice(start, nodes_number-1, 1)))

    def __repr__(self):
        return f"Path(path_cost={self.path_cost}, nodes={self.nodes}, layers={self.layers}, services={self.mobility_services})"

    def __eq__(self, other: "Path"):
        same_nodes = (self.nodes == other.nodes)
        same_ms = (self.mobility_services == other.mobility_services)
        return same_nodes and same_ms

    def __deepcopy__(self, memo={}):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, deepcopy(v, memo))
        return result

    def __copy__(self):
        cls = self.__class__
        result = cls.__new__(cls)
        result.__dict__.update(self.__dict__)
        return result

    def update_path_cost(self, mlgraph, cost):
        """Method that recomputes and updates path cost.

        Args:
            -mlgraph: graph where path is defined
            -cost: name of the cost to consider
        """
        path_cost = 0
        for i,(lid, sl) in enumerate(self.layers):
            ms = self.mobility_services[i]
            for j in range(sl.start, sl.stop-1):
                un = self.nodes[j]
                dn = self.nodes[j+1]
                path_cost += mlgraph.graph.nodes[un].adj[dn].costs[ms][cost]
        self.path_cost = path_cost

    def increment_path_cost(self, additional_cost):
        """Method that adds an additional cost value to the current path cost.

        Args:
            -additional_cost: the cost to add
        """
        self.path_cost += additional_cost
