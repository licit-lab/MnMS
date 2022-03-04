from typing import Union, List, Tuple

from mnms.tools.time import Time
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
    def __init__(self, id: str, origin: Union[str, np.ndarray], destination: Union[str, np.ndarray], departure_time: Time,
                 available_mobility_services=None,
                 scale_factor=1,
                 path=None) -> object:
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
    def vehicle(self):
        return self._vehicle

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

    def set_position(self, current_link:Tuple[str, str], remaining_length:float):
        self._current_link = current_link
        self._remaining_link_length = remaining_length
