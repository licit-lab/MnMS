from copy import deepcopy
from typing import Union, List, Tuple

from mnms.time import Time
from mnms.tools.observer import TimeDependentSubject

import numpy as np


class User(TimeDependentSubject):
    """User data class

    Parameters
    ----------
    id: str
        Id of the User
    origin: str
        Origin of the User
    destination:
        Desitnation of the User
    departure_time: Time
        Departure time of the User
    available_mobility_services: List[str]
        List of available services by the User (default all mode are accessible)
    scale_factor: int
        Scale factor, one User can count for multiple User
    path: List[str]
        Path from origin to destination

    """
    def __init__(self,
                 id: str,
                 origin: Union[str, np.ndarray],
                 destination: Union[str, np.ndarray],
                 departure_time: Time,
                 available_mobility_services=None,
                 scale_factor=1,
                 path=None):
        super(User, self).__init__()
        self.id = id
        self.origin = origin
        self.destination = destination
        self.departure_time = departure_time
        self.arrival_time = None
        self.available_mobility_service = available_mobility_services if available_mobility_services is None else set(available_mobility_services)
        self.scale_factor = scale_factor

        self._current_link = None
        self._remaining_link_length = None
        self._position = None

        self._vehicle = None
        self._waiting_vehicle = False
        self._current_node = None
        if path is None:
            self.path = None
        else:
            self.set_path(path)

    def __repr__(self):
        return f"User('{self.id}', {self.origin}->{self.destination}, {self.departure_time})"

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

    def set_path(self, path:"Path"):
        self.path = path
        self._current_node = path.nodes[0]
        self._current_link = (path.nodes[0], path.nodes[1])

    def set_position(self, current_link:Tuple[str, str], remaining_length:float, position:np.ndarray):
        self._current_link = current_link
        self._remaining_link_length = remaining_length
        self._position = position


class Path(object):
    def __init__(self, cost=None, nodes: List[str] = None):
        self.path_cost: float = cost
        self.layers: List[Tuple[str, slice]] = list()
        self.mobility_services = list()
        self.nodes: List[str] = nodes
        self.service_costs = dict()

    def construct_layers(self, gnodes):
        layer = gnodes[self.nodes[1]].label
        start = 1
        nodes_number = len(self.nodes)
        for i in range(2, nodes_number-1):
            ilayer = gnodes[self.nodes[i]].label
            if ilayer != layer:
                self.layers.append((layer, slice(start, i, 1)))
                layer = ilayer
                start = i
        self.layers.append((layer, slice(start, nodes_number-1, 1)))

    def __repr__(self):
        return f"Path(path_cost={self.path_cost}, nodes={self.nodes}, layers={self.layers}, services={self.mobility_services})"

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, deepcopy(v, memo))
        return result
