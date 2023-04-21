from collections import defaultdict
from copy import deepcopy
from enum import Enum
from typing import Union, List, Tuple, Optional, Dict

from mnms.time import Time, Dt
from mnms.tools.observer import TimeDependentSubject

import numpy as np


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
                 path: Optional["Path"] = None,
                 response_dt: Optional[Dt] = None,
                 pickup_dt: Optional[Dt] = None,
                 continuous_journey: Optional[str] = None):
        """
        Class representing a User in the simulation.

        Parameters
        ----------
        _id: The unique id of the User
        origin: The origin of the User
        destination: the destination of the User
        departure_time: The departure time
        available_mobility_services: The available mobility services
        path: The path of the User
        response_dt: The maximum dt a User is ok to wait from a mobility service
        pickup_dt: The maximu dt a User is ok to wait for a pick up
        continuous_journey: If not None, the User restarted its journey
        """
        super(User, self).__init__()
        self.id = _id
        self.origin = origin if not isinstance(origin, list) else np.array(origin)
        self.destination = destination if not isinstance(destination, list) else np.array(destination)
        self.departure_time = departure_time
        self.arrival_time = None
        self.available_mobility_service = available_mobility_services if available_mobility_services is None else set(available_mobility_services)
        self.scale_factor = 1

        self._current_link = None
        self._remaining_link_length = None
        self._position = None

        self._vehicle = None
        self._waiting_vehicle = False
        self._current_node = None
        self._distance = 0

        self._state = UserState.STOP

        self.response_dt = User.default_response_dt.copy() if response_dt is None else response_dt
        self.pickup_dt = defaultdict(lambda: User.default_pickup_dt.copy() if response_dt is None else lambda: pickup_dt)

        self._continuous_journey = continuous_journey
        self.parameters: Dict = dict()

        if path is None:
            self.path: Optional[Path] = None
        else:
            self.set_path(path)

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
        # self.notify()

    def set_path(self, path: "Path"):
        self.path: Path = path
        self._current_node = path.nodes[0]
        self._current_link = (path.nodes[0], path.nodes[1])

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

    def set_state_deadend(self):
        self._state = UserState.DEADEND


class Path(object):
    def __init__(self, ind: int, cost: float=None, nodes: Union[List[str], Tuple[str]] = None):
        """
        Path object describing a User path in the simulation
        Parameters
        ----------
        ind: The index of the path (multiple path are computed for one User)
        cost: The cost of the path
        nodes: The nodes describing the path
        """
        self.ind = ind
        self.path_cost: float = cost
        self.layers: List[Tuple[str, slice]] = list()
        self.mobility_services = list()
        self.nodes: Tuple[str] = nodes
        self.service_costs = dict()

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
        return self.nodes == other.nodes

    def __deepcopy__(self, memo={}):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, deepcopy(v, memo))
        return result
