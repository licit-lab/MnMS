from typing import Union, List

from mnms.tools.time import Time
from mnms.tools.observer import Subject

import numpy as np


class User(Subject):
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
                 path=None):
        super(User, self).__init__()
        self.id = id
        self.origin = origin
        self.destination = destination
        self.departure_time = departure_time
        self.arrival_time = None
        self.path = path
        self.path_cost = None
        self.available_mobility_service = available_mobility_services
        self.scale_factor = scale_factor

    def __repr__(self):
        return f"User('{self.id}', {self.origin}->{self.destination}, {self.departure_time})"

    def notify(self):
        p = ' '.join(self.path) if self.path is not None else None
        for obs in self._observers:
            obs.update(id=self.id,
                       origin=self.origin,
                       destination=self.destination,
                       departure_time=self.departure_time,
                       arrival_time=self.arrival_time,
                       path=p,
                       cost_path=self.path_cost)
    
    def finish_trip(self, arrival_time:Time):
        self.arrival_time = arrival_time
        self.notify()
