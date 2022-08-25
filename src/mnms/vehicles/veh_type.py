from collections import deque
from typing import List, Tuple, Deque, Optional, Generator, Callable
from enum import Enum
from dataclasses import dataclass, field

import numpy as np

from mnms.tools.observer import TimeDependentSubject
from mnms.log import create_logger
from mnms.time import Time

log = create_logger(__name__)
_norm = np.linalg.norm


_TYPE_ITEM_PATH = Tuple[Tuple[str, str], float]
_TYPE_PATH = List[_TYPE_ITEM_PATH]


class VehicleState(Enum):
    STOP = 0
    REPOSITIONING = 1
    PICKUP = 2
    SERVING = 3


@dataclass
class VehicleActivity(object):
    state: VehicleState
    node: str
    path: _TYPE_PATH = field(default_factory=list)
    user: "User" = None
    is_done: bool = False
    iter_path: Generator[_TYPE_ITEM_PATH, None, None] = field(default=None, init=False)

    def __post_init__(self):
        self.reset_path_iterator()

    def reset_path_iterator(self):
        self.iter_path = iter(self.path)

    def modify_path(self, new_path:_TYPE_PATH):
        self.path = new_path
        self.reset_path_iterator()

    def done(self, veh: "Vehicle"):
        return None

    def start(self, veh: "Vehicle"):
        return None


@dataclass
class VehicleActivityStop(VehicleActivity):
    state: VehicleState = field(default=VehicleState.STOP, init=False)

    def start(self, veh: "Vehicle"):
        # if self.user is not None:
        #     veh._vehicle = veh
        return None

    def done(self, veh: "Vehicle"):
        if self.user is not None:
            veh._vehicle = veh


@dataclass
class VehicleActivityRepositioning(VehicleActivity):
    state: VehicleState = field(default=VehicleState.REPOSITIONING, init=False)

    def start(self, veh: "Vehicle"):
        return None

    def done(self, veh: "Vehicle"):
        return None


@dataclass
class VehicleActivityPickup(VehicleActivity):
    state: VehicleState = field(default=VehicleState.PICKUP, init=False)

    def start(self, veh: "Vehicle"):
        self.user._waiting_vehicle = True
        self.user.set_state_waiting_vehicle()

    def done(self, veh: "Vehicle"):
        self.user._waiting_vehicle = False
        self.user._vehicle = veh
        veh.passenger[self.user.id] = self.user
        self.user.set_state_inside_vehicle()


@dataclass
class VehicleActivityServing(VehicleActivity):
    state: VehicleState = field(default=VehicleState.SERVING, init=False)

    def start(self, veh: "Vehicle"):
        self.user._waiting_vehicle = False
        self.user._vehicle = veh
        veh.passenger[self.user.id] = self.user
        self.user.set_state_inside_vehicle()

    def done(self, veh: "Vehicle"):
        self.user._waiting_vehicle = False
        self.user._vehicle = None
        veh.passenger.pop(self.user.id)

        self.user._remaining_link_length = 0
        upath = self.user.path.nodes
        unode = veh._current_link[1]
        self.user._current_node = unode
        next_node_ind = upath.index(unode)+1
        self.user.set_position((unode, upath[next_node_ind]), 0, veh.position)
        self.user._vehicle = None
        # self.user._vehicle = None
        # self.user.notify(tcurrent)
        self.user.set_state_stop()



class Vehicle(TimeDependentSubject):
    _counter = 0

    def __init__(self,
                 node: str,
                 capacity: int,
                 activities: Optional[List[VehicleActivity]] = None):

        super(Vehicle, self).__init__()
        self._global_id = str(Vehicle._counter)
        Vehicle._counter += 1

        self._capacity = capacity
        self.passenger = dict()

        self._current_link = None
        self._current_node = node
        self._remaining_link_length = None
        self._position = None
        self._distance = 0
        self.speed = 0

        self.activities: Deque[VehicleActivity] = deque([])
        self.activity = None

        if activities is not None:
            self.add_activities(activities)
            self.next_activity()
        else:
            self.activity: VehicleActivity = self.default_activity()

    def __repr__(self):
        return f"{self.__class__.__name__}('{self._global_id}', '{self.state.name}')"

    @property
    def distance(self):
        return self._distance

    @property
    def is_full(self):
        return len(self.passenger) >= self._capacity

    @property
    def is_empty(self):
        return not bool(self.passenger)

    @property
    def id(self):
        return self._global_id

    @property
    def type(self):
        return self.__class__.__name__

    @property
    def current_link(self):
        return self._current_link

    @property
    def remaining_link_length(self):
        return self._remaining_link_length

    @property
    def position(self):
        return self._position

    @property
    def state(self) -> VehicleState:
        return self.activity.state if self.activity is not None else None

    def add_activities(self, activities:List[VehicleActivity]):
        for a in activities:
            self.activities.append(a)

    def next_activity(self):
        if self.activity is not None:
            self.activity.done(self)

        try:
            activity = self.activities.popleft()
        except IndexError:
            activity = self.default_activity()

        self.activity = activity
        self.activity.start(self)
        if activity.state is not VehicleState.STOP:
            if activity.path:
                self._current_link, self._remaining_link_length = next(activity.iter_path)
                assert self._current_node == self._current_link[0]
            else:
                activity.is_done = True

            # self._current_node = self._current_link[0]

    def set_path(self, path: List[Tuple[Tuple[str, str], float]]):
        self._iter_path = iter(path)
        self._current_link, self._remaining_link_length = next(self._iter_path)

    def update_distance(self, dist: float):
        self._distance += dist
        for user in self.passenger.values():
            user.update_distance(dist)

    def set_position(self, position: np.ndarray):
        self._position = position

    def drop_user(self, tcurrent:Time, user:'User', drop_pos:np.ndarray):
        log.info(f"{user} is dropped at {self._current_link[0]}")
        user._remaining_link_length = 0
        upath = user.path.nodes
        unode = self._current_link[0]
        user._current_node = unode
        next_node_ind = upath.index(unode)+1
        user.set_position((unode, upath[next_node_ind]), 0, drop_pos)
        user._vehicle = None
        user.notify(tcurrent)

        del self.passenger[user.id]

    def drop_all_passengers(self, tcurrent:Time):
        for _, user in self.passenger.values():
            log.info(f"{user} is dropped at {self._current_link[1]}")
            unode = self._current_link[1]
            user._current_node = unode
            user._remaining_link_length = 0
            user._position = self._position
            user.notify(tcurrent)
            user._vehicle = None

        self.passenger = dict()

    def start_user_trip(self, userid, take_node):
        log.info(f'Passenger {userid} has been taken by {self} at {take_node}')
        take_time, user = self._next_passenger.pop(userid)
        user._vehicle = self.id
        user._waiting_vehicle = False
        self.passenger[userid] = (take_time, user)

    def default_activity(self):
        return VehicleActivityStop(node=self._current_link[0],
                                   path=[],
                                   is_done=False)

    def notify_passengers(self, tcurrent: Time):
        for user in self.passenger.values():
            user.notify(tcurrent)


class Car(Vehicle):
    def __init__(self,
                 node: str,
                 capacity: int,
                 activity: Optional[VehicleActivity] = None):
        super(Car, self).__init__(node, capacity, activity)


class Bus(Vehicle):
    def __init__(self,
                 node: str,
                 capacity: int,
                 activity: Optional[VehicleActivity] = None):
        super(Bus, self).__init__(node, capacity, activity)

class Tram(Vehicle):
    def __init__(self,
                 node: str,
                 capacity: int,
                 activity: Optional[VehicleActivity] = None):
        super(Tram, self).__init__(node, capacity, activity)


class Metro(Vehicle):
    def __init__(self,
                 node: str,
                 capacity: int,
                 activity: Optional[VehicleActivity] = None):
        super(Metro, self).__init__(node, capacity, activity)