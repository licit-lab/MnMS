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
                 _id: str,
                 origin: Union[str, Union[np.ndarray, List]],
                 destination: Union[str, Union[np.ndarray, List]],
                 departure_time: Time,
                 available_mobility_services=None,
                 mobility_services_graph: str=None,
                 path: Optional["Path"] = None,
                 response_dt: Optional[Dt] = None,
                 pickup_dt: Optional[Dt] = None,
                 continuous_journey: Optional[str] = None,
                 forced_path_chosen_mobility_services: Optional[Dict[str,str]] = None):
        """
        Class representing a User in the simulation.

        Parameters
        ----------
        _id: The unique id of the User
        origin: The origin of the User
        destination: the destination of the User
        departure_time: The departure time
        available_mobility_services: The available mobility services
        mobility_services_graph: Id of the mobility services graph
                                        to use for this traveler
        path: The path of the User
        response_dt: The maximum dt a User is ok to wait from a mobility service
        pickup_dt: The maximum dt a User is ok to wait for a pick up
        continuous_journey: If not None, the User restarted its journey
        forced_path_chosen_mobility_services: Dict with layers ids as keys and chosen
            mobility services id on each layer as values, it is used when one want to
            force the initial path of a user with the CSVDemandManager
        """
        super(User, self).__init__()
        self.id = _id
        self.origin = origin if not isinstance(origin, list) else np.array(origin)
        self.destination = destination if not isinstance(destination, list) else np.array(destination)
        self.departure_time = departure_time
        self.arrival_time = None
        self.available_mobility_services = available_mobility_services if available_mobility_services is None else set(available_mobility_services)
        self.mobility_services_graph = mobility_services_graph

        self._current_link = None
        self._remaining_link_length = None
        self._position = None
        self._achieved_path = list()

        self._vehicle = None
        self._parked_personal_vehicles = dict()
        self._waiting_vehicle = False
        self._current_node = None
        self._distance = 0
        self._interrupted_path = None

        self._state = UserState.STOP

        self.response_dt = User.default_response_dt.copy() if response_dt is None else response_dt
        self.pickup_dt = defaultdict(lambda: User.default_pickup_dt.copy() if pickup_dt is None else lambda: pickup_dt)

        self._continuous_journey = continuous_journey
        self.parameters: Dict = dict()

        if path is None:
            self.path: Optional[Path] = None
            self.forced_path_chosen_mobility_services = None
        else:
            self.set_path(path)
            self.forced_path_chosen_mobility_services = forced_path_chosen_mobility_services

    def __repr__(self):
        return f"User('{self.id}', {self.origin}->{self.destination}, {self.departure_time})"

    @property
    def state(self):
        return self._state

    @property
    def distance(self):
        return self._distance

    @property
    def position(self):
        return self._position

    @property
    def vehicle(self):
        return self._vehicle

    @property
    def current_node(self):
        return self._current_node

    @property
    def is_in_vehicle(self):
        return self._vehicle is not None

    @property
    def achieved_path(self):
        return self._achieved_path

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
        cnode_ind = list(np.where(np.array(path_nodes) == self._current_node)[0])
        if len(cnode_ind) == 0:
            return -1
        if len(cnode_ind) == 1:
            cnode_ind = cnode_ind[0]
        else:
            c = self._achieved_path.count(self._current_node)
            if c == 0:
                cnode_ind = cnode_ind[0]
            else:
                cnode_ind = cnode_ind[c-1]
        return cnode_ind

    def get_node_index_in_path(self, node):
        """Method that finds the index of a node in user's path considering the path
        already achieved. The index of node returned should not be already passed by user.

        Args:
            -node: the node to find the index of

        Returns:
            -ind: the index of the node in user's path, -1 if node has not been found
        """
        node_inds = list(np.where(np.array(self.path.nodes) == node)[0])
        if len(node_inds) == 0:
            return -1
        if len(node_inds) == 1:
            ind = node_inds[0]
        else:
            c = self._achieved_path.count(node)
            if c == 0:
                ind = node_inds[0]
            else:
                ind = node_inds[c]
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

    def update_path(self, path: "Path", gnodes, mlgraph, cost: str):
        """Method that updates the path of user.

        Args:
            -path: path that should starts with a node belonging to user's current path
                   that has not already been passed by the user. This path will replace
                   all the nodes located after this common node in user's current path.
            -gnodes: multilayergraph nodes
            -mlgraph: multilayergraph
            -cost: name of the cost user considers
        """
        # Small check on new path consistency
        current_node_ind = self.get_current_node_index()
        path_first_node_ind = self.get_node_index_in_path(path.nodes[0])
        assert path_first_node_ind >= current_node_ind, f'User {self.id} tried to update path at an index already achieved'

        # Build user's new path
        new_path_nodes = self.path.nodes[:path_first_node_ind] + path.nodes
        new_path = Path(None, new_path_nodes)
        new_path.construct_layers_from_links(gnodes)
        new_mobservices = [self.path.mobility_services[i] for i,(lid,sl) in enumerate(self.path.layers) if \
            path_first_node_ind >= sl.stop or (path_first_node_ind > sl.start and path_first_node_ind < sl.stop)]
        if new_mobservices[-1] == path.mobility_services[0]:
            new_mobservices.extend(path.mobility_services[1:])
            current_layer = [(lid,sl) for lid,sl in new_path.layers if current_node_ind >= sl.start and path_first_node_ind < sl.stop][0]
            new_drop_node = new_path_nodes[current_layer[1].stop-1]
        else:
            new_mobservices.extend(path.mobility_services)
            new_drop_node = path.nodes[0]
        new_path.set_mobility_services(new_mobservices)
        new_path.update_path_cost(mlgraph, cost)
        service_costs = sum_dict(*(mlgraph.layers[layer].mobility_services[service].service_level_costs(new_path.nodes[node_inds]) \
            for (layer, node_inds), service in zip(new_path.layers, new_path.mobility_services) if service != 'WALK'))
        new_path.service_costs = service_costs

        # Set user's new path
        self.path = new_path

        # Return the new drop node of user for the vehicle she currently is inside
        return new_drop_node

    def update_path_and_current_vehicle_plan(self, path: "Path", gnodes, mlgraph, cost: str):
        """Method that updates the path of a user who is current inside a vehicle.

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
        # Small check on method call consistency
        assert self._vehicle is not None, 'Wrong call of update_path_and_current_vehicle_plan method; user should be inside a vehicle...'

        # Find user serving activity in vehicle's plan and former drop node
        all_activities = [self._vehicle.activity] + list(self._vehicle.activities)
        u_serving_act_ind = [i for i in range(len(all_activities)) if all_activities[i].user == self][0] # pickup activity already done because user is in the veh
        former_drop_node = all_activities[u_serving_act_ind].node

        # Differentiate update plan of public transport and non public transport vehicles
        veh_ms = self._vehicle.mobility_service
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
            path_first_node_pos = gnodes[path.nodes[0]].position
            dist = _norm(np.array(teleport_origin) - np.array(path_first_node_pos))
            if dist <= max_teleport_dist and dist > 0:
                log.warning(f'User {self.id} teleport from {self._current_node} to {path.nodes[0]} for {dist} meters')
            elif dist > max_teleport_dist and dist > 0:
                log.error(f'User {self.id} tried to teleport from {self._current_node} to {path.nodes[0]} for {dist} meters: it is prohibited ! ')
                sys.exit(-1)
        self.path: Path = path
        self._current_node = path.nodes[0]
        self._current_link = (path.nodes[0], path.nodes[1])

    def start_path(self, gnodes):
        self._remaining_link_length = gnodes[self.path.nodes[0]].adj[self.path.nodes[1]].length

    def interrupt_path(self, tcurrent: Time):
        """Method that interrupts user's current path.

        Args:
            -tcurrent: time at which user stopped to follow her path
        """
        self.set_state_stop()
        self._interrupted_path = copy(self.path)
        self.path = None
        self.notify(tcurrent)

    def set_position(self, current_link:Tuple[str, str], current_node:str, remaining_length:float, position:np.ndarray):
        """Method that updates user's position (including current node, link,
        remaining link length, position and achieved path).

        Args:
            -current_link: user's new current link
            -current_node: user's new current node
            -remaining_length: remaining length to travel on current link
            -position: coordinates of user's new position
        """
        self._current_node = current_node
        self._current_link = current_link
        self._remaining_link_length = remaining_length
        self._position = position
        self.update_achieved_path(current_node)

    def set_position_only(self, position:np.ndarray):
        self._position = position

    def set_remaining_link_length(self, l):
        self._remaining_link_length = l

    def set_current_link(self, l):
        self._current_link = l

    def set_current_node(self, n):
        self._current_node = n

    def update_achieved_path(self, reached_node):
        """Method that update user's achieved path with the new reached node.

        Args:
            -reached_node: node user has just reached
        """
        if len(self._achieved_path) == 0 or reached_node != self._achieved_path[-1]:
            self._achieved_path.append(reached_node)


    def update_distance(self, dist: float):
        """Method that increments the distance traveled by user.

        Args:
            -dist: the distance to add
        """
        self._distance += dist

    def set_state_arrived(self):
        self._state = UserState.ARRIVED

    def set_state_walking(self):
        self._state = UserState.WALKING

    def set_state_inside_vehicle(self):
        self._state = UserState.INSIDE_VEHICLE

    def set_state_waiting_vehicle(self):
        self._state = UserState.WAITING_VEHICLE

    def set_state_waiting_answer(self):
        self._state = UserState.WAITING_ANSWER

    def set_state_stop(self):
        self._state = UserState.STOP

    def set_state_deadend(self, tcurrent: Time):
        self._state = UserState.DEADEND
        self._waiting_vehicle = False
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
        assert ((self._interrupted_path is not None) and (self._current_node is not None)), \
            f'Cannot find back the mobility service for which user {self.id} undergone a match failure'
        upath = self._interrupted_path.nodes
        ind_current_node = self.get_current_node_index(upath)
        for ilayer, (layer, slice_nodes) in enumerate(self._interrupted_path.layers):
            if slice_nodes.start == ind_current_node:
                failed_mservice = self._interrupted_path.mobility_services[ilayer]
                return failed_mservice
        log.error(f'Could not find back the mobility service for which user {self.id} undergone a match failure')
        sys.exit(-1)

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
