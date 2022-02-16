from typing import List, Dict, Tuple


class Vehicle(object):
    _counter = 0

    def __init__(self,
                 origin:str,
                 destination:str,
                 path: List[Tuple[Tuple[str, str], float]],
                 capacity:int):

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

    def take_user(self, user:str):
        self._passenger[user.id] = user

    def drop_user(self, user:str):
        del self._passenger[user.id]

    def set_speed(self, speed:float):
        self._speed = speed

    def move(self, dist: float):
        dist_travelled = self._remaining_link_length - dist
        if dist_travelled < 0:
            try:
                self._current_link, self._remaining_link_length = next(self._iter_path)
                self.move(abs(dist_travelled))
            except StopIteration:
                self._remaining_link_length = 0
                self.is_arrived = True
        else:
            self._remaining_link_length = dist_travelled

        return self._current_link


class Car(Vehicle):
    def __init__(self, origin:str, destination:str, path: List[Tuple[Tuple[str, str], float]], capacity:int=5):
        super(Car, self).__init__(origin, destination, path, capacity)


class Bus(Vehicle):
    def __init__(self, origin:str, destination:str, path: List[Tuple[Tuple[str, str], float]], capacity:int=50):
        super(Bus, self).__init__(origin, destination, path, capacity)


class Subway(Vehicle):
    def __init__(self, origin:str, destination:str, path: List[Tuple[Tuple[str, str], float]], capacity:int=500,):
        super(Subway, self).__init__(origin, destination, path, capacity)


if __name__ == "__main__":
    veh = Car('C0', 'C3', [(('C0', 'C1'), 1), (('C1', 'C2'), 1), (('C2', 'C3'), 1)])
    # for i in range(31):
    #     veh.move(0.1)
    #     print(i, veh._current_link, veh._remaining_link_length)

    veh.move(2.5)
    print(veh._current_link, veh._remaining_link_length)