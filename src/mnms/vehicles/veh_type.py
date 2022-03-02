from typing import List, Dict, Tuple

from mnms.tools.observer import TimeDependentSubject
from mnms.log import create_logger
from mnms.tools.time import Time, Dt

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
        self._next_passenger = dict()

        self._iter_path = iter(path)
        self._current_link, self._remaining_link_length = next(self._iter_path)

        self.path = path
        self.origin = origin
        self.destination = destination
        self.speed = None

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

    def take_next_user(self, user:'User', drop_node:str):
        # user._vehicle = self.id
        log.info(f"{user} will be taken by {self} at {user._current_node} and will be drop at {drop_node}")
        self._next_passenger[user.id] = (drop_node, user)
        user._waiting_vehicle = True

    def drop_user(self, tcurrent:Time, user:'User'):
        log.info(f"{user} is dropped at {self._current_link[0]}")
        user._vehicle = None
        upath = user.path
        unode = self._current_link[0]
        user._current_node = unode
        next_node_ind = upath.index(unode)+1
        user.set_position((unode, upath[next_node_ind]), 0)
        user.notify(tcurrent)
        del self._passenger[user.id]

    def drop_all_passengers(self, tcurrent:Time):
        for _, user in self._passenger.values():
            log.info(f"{user} is dropped at {self._current_link[1]}")
            user._vehicle = None
            unode = self._current_link[1]
            user._current_node = unode
            user._remaining_link_length = 0
            user.notify(tcurrent)

        self._passenger = dict()

    def start_user_trip(self, userid, take_node):
        log.info(f'Passenger {userid} has been taken by {self} at {take_node}')
        take_time, user = self._next_passenger.pop(userid)
        user._vehicle = self.id
        user._waiting_vehicle = False
        self._passenger[userid] = (take_time, user)



    def move(self, tcurrent: Time, dt:Dt, speed:float):
        # log.info(f"START MOVE {dt}")
        # self.notify(tcurrent)
        # for _, user in self._passenger.values():
        #     user.notify(tcurrent)

        self.started = True
        dist_travelled = dt.to_seconds()*speed
        # log.info(f"TRAVEL {dist_travelled}")
        for next_pass in list(self._next_passenger):
            log.info(self._next_passenger)
            take_node = self._next_passenger[next_pass][1]._current_node
            if take_node == self._current_link[0]:
                self.start_user_trip(next_pass, take_node)

        if dist_travelled > self._remaining_link_length:
            elapsed_time = Dt(seconds=self._remaining_link_length / speed)
            try:
                # log.info(f"{dist_travelled}, {self._remaining_link_length}")
                self._current_link, self._remaining_link_length = next(self._iter_path)
                # log.info(f"{dist_travelled}, {self._remaining_link_length}")

                # log.info(f"TIMINGS {dt}, {elapsed_time} {tcurrent}, {tcurrent.add_time(elapsed_time)}")
                new_dt = dt - elapsed_time
                # log.info(f"TIMINGS {dt}, {elapsed_time} {tcurrent}, {tcurrent.add_time(elapsed_time)}")
                self.move(tcurrent.add_time(elapsed_time), new_dt, speed)
            except StopIteration:
                log.info(f"{self} is arrived")
                self._remaining_link_length = 0
                self.is_arrived = True
                self.drop_all_passengers(tcurrent.add_time(elapsed_time))
                self.notify(tcurrent.add_time(elapsed_time))
                return
        else:
            elapsed_time = dt
            self._remaining_link_length -= dist_travelled

        user_to_drop = list()
        for passenger_id, (drop_node, passenger) in self._passenger.items():
            if drop_node == self._current_link[0]:
                user_to_drop.append(passenger)
        [self.drop_user(tcurrent.add_time(elapsed_time), passenger) for passenger in user_to_drop]

        for _, user in self._passenger.values():
            user.set_position(self._current_link, self._remaining_link_length)

        # self.notify(tcurrent.add_time(elapsed_time))
        self.notify(tcurrent)
        for _, user in self._passenger.values():
            user.notify(tcurrent)
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

