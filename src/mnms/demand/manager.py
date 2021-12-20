from typing import List


class DemandManager(object):
    def __init__(self, users):
        self._users = users
        self._iter_demand = iter(self._users)
        self._current_user = next(self._iter_demand)

        self.nb_users = len(self._users)

    @classmethod
    def fromCSV(cls):
        pass

    # TODO
    def toCSV(self, file):
        raise NotImplementedError

    def get_next_departure(self, tstart, tend) -> List['User']:
        departure = list()
        while tstart <= self._current_user.departure_time < tend:
            departure.append(self._current_user)
            try:
                self._current_user = next(self._iter_demand)
            except StopIteration:
                return departure
        return departure
