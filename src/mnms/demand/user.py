from collections import defaultdict
from copy import copy, deepcopy
from enum import Enum
from typing import Union, List, Tuple, Optional, Dict

from mnms.time import Time, Dt
from mnms.tools.observer import TimeDependentSubject
from mnms.log import create_logger

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

    def finish_trip(self, arrival_time:Time):
        self.arrival_time = arrival_time
        self.set_state_arrived()
        log.info(f"User {self.id} arrived at destination at {arrival_time}")
        # self.notify()

    def set_pickup_dt(self, ms, dt):
        self.pickup_dt[ms] = dt

    def set_available_mobility_services(self, ams):
        self.available_mobility_services = ams
        log.info(f'User {self.id} updated list of available mobility services to {self.available_mobility_services}')

    def remove_available_mobility_service(self, ms):
        self.available_mobility_services.remove(ms)
        log.info(f'User {self.id} updated list of available mobility services to {self.available_mobility_services}')

    def update_path(path: "Path", gnodes, mlgraph, cost: str):
        """Method that update the path of user.

        Args:
            -path: path that should starts with a node belonging to user's current path
                   that has not already been passed by the user. This path will replace
                   all the nodes located after this common node in user's current path.
            -gnodes: multilayergraph nodes
            -mlgraph: multilayergraph
            -cost: name of the cost user considers
        """
        current_node_ind = self.path.nodes.index(self._current_node)
        path_first_node_ind = self.path.nodes.index(path.nodes[0])
        assert path_first_node_ind >= current_node_ind, f'User {self.id} tried to update path at an index already achieved'
        new_path_nodes = self.path.nodes[:path_first_node_ind] + path.nodes
        new_mobservices = [self.path.mobility_services[i] for i,(lid,sl) in enumerate(self.path.layers) if \
            path_first_node_ind >= sl.stop or (path_first_node_ind > sl.start and path_first_node_ind < sl.stop)] + path.mobility_services
        new_path = Path(new_path_cost, None)
        new_path.construct_layers_from_links(gnodes)
        new_path.set_mobility_services(new_mobservices)
        new_path_cost = new_path.update_path_cost(mlgraph, cost)
        service_costs = sum_dict(*(mlgraph.layers[layer].mobility_services[service].service_level_costs(new_path.nodes[node_inds]) \
            for (layer, node_inds), service in zip(new_path.layers, new_path.mobility_services) if service != 'WALK'))
        new_path.service_costs = service_costs

        self.path = new_path


    def set_path(self, path: "Path", gnodes = None, max_teleport_dist: float = 0., teleport_origin = None):
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
        self.set_state_stop()
        self._interrupted_path = copy(self.path)
        self.path = None
        self.notify(tcurrent)

    def set_position(self, current_link:Tuple[str, str], remaining_length:float, position:np.ndarray):
        self._current_link = current_link
        self._remaining_link_length = remaining_length
        self._position = position

    def update_distance(self, dist: float):
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
        assert ((self._interrupted_path is not None) and (self._current_node is not None)), \
            f'Cannot find back the mobility service for which user {self.id} undergone a match failure'
        upath = self._interrupted_path.nodes
        ind_current_node = upath.index(self._current_node)
        for ilayer, (layer, slice_nodes) in enumerate(self._interrupted_path.layers):
            if slice_nodes.start == ind_current_node:
                failed_mservice = self._interrupted_path.mobility_services[ilayer]
                return failed_mservice
        else:
            log.error(f'Could not find back the mobility service for which user {self.id} undergone a match failure')
            sys.exit(-1)

    def park_personal_vehicle(self, ms, node):
        """Method that register the mobility service and the parking location of user's
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
        path_cost = 0
        for i,(lid, sl) in enumerate(self.layers):
            ms = self.mobility_services[i]
            for j in range(sl.start, sl.stop-1):
                un = path_nodes[j]
                dn = path_nodes[j+1]
                path_cost += mlgraph.graph.nodes[un].adj(dn).costs[ms][cost]
        self.path_cost = path_cost
