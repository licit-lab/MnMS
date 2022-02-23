from typing import List, Dict, Tuple

from mnms.tools.observer import TimeDependentSubject
from mnms.log import create_logger

log = create_logger(__name__)

class Vehicle(TimeDependentSubject):
    _counter = 0

    def __init__(self,
                 origin:str,
                 destination:str,
                 path: List[Tuple[Tuple[str, str], float]],
                 capacity:int):

        super(Vehicle, self).__init__()
        self._global_id = str(Vehicle._counter)
        Vehicle._counter += 1

        self._capacity = capacity
        self._passenger = dict()

        self._iter_path = iter(path)
        self._current_link, self._remaining_link_length = next(self._iter_path)

        self.path = path
        self.origin = origin
        self.destination = destination

        self.is_arrived = False
        self.started = False

    def __repr__(self):
        return f"{self.__class__.__name__}('{self._global_id}', '{self.origin}' -> '{self.destination}')"

    @property
    def is_full(self):
        return len(self._passenger) >= self._capacity

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

    def take_user(self, user:'User'):
        user._vehicle = self.id
        self._passenger[user.id] = user

    def drop_user(self, user:'User'):
        user._vehicle = None
        user._current_node = self._current_link[1]
        del self._passenger[user.id]

    def drop_all_passengers(self):
        [self.drop_user(u) for u in list(self._passenger.values())]

    def move(self, dist: float):
        self.started = True
        dist_travelled = self._remaining_link_length - dist
        if dist_travelled < 0:
            try:
                self._current_link, self._remaining_link_length = next(self._iter_path)
                self.move(abs(dist_travelled))
            except StopIteration:
                log.info(f"{self} is arrived")
                self._remaining_link_length = 0
                self.is_arrived = True
        else:
            self._remaining_link_length = dist_travelled
        for p in self._passenger.values():
            p._current_node = self._current_link[0]
        return self._current_link


class Car(Vehicle):
    def __init__(self, origin:str, destination:str, path: List[Tuple[Tuple[str, str], float]], capacity:int=5):
        super(Car, self).__init__(origin, destination, path, capacity)


class Bus(Vehicle):
    def __init__(self, origin:str, destination:str, path: List[Tuple[Tuple[str, str], float]], capacity:int=50):
        super(Bus, self).__init__(origin, destination, path, capacity)


class Metro(Vehicle):
    def __init__(self, origin:str, destination:str, path: List[Tuple[Tuple[str, str], float]], capacity:int=500,):
        super(Metro, self).__init__(origin, destination, path, capacity)


if __name__ == "__main__":
    veh = Car('C0', 'C3', [(('C0', 'C1'), 1), (('C1', 'C2'), 1), (('C2', 'C3'), 1)])

