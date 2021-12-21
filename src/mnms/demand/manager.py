import csv
from typing import List
from abc import ABC, abstractmethod

from mnms.demand.user import User
from mnms.tools.time import Time


class AbstractDemandManager(ABC):
    @abstractmethod
    def get_next_departures(self, tstart:Time, tend: Time) -> List[User]:
        pass


class BaseDemandManager(ABC):
    def __init__(self, users):
        self._users = users
        self._iter_demand = iter(self._users)
        self._current_user = next(self._iter_demand)

        self.nb_users = len(self._users)

    def get_next_departures(self, tstart:Time, tend:Time) -> List[User]:
        departure = list()
        while tstart <= self._current_user.departure_time < tend:
            departure.append(self._current_user)
            try:
                self._current_user = next(self._iter_demand)
            except StopIteration:
                return departure
        return departure


class CSVDemandManager(AbstractDemandManager):
    def __init__(self, csvfile, delimiter=';'):
        self._filename = csvfile
        self._file = open(self._filename, 'r')
        self._reader = csv.reader(self._file, delimiter=delimiter, quotechar='|')

        next(self._reader)
        self._current_user = self.construct_user(next(self._reader))

    def get_next_departures(self, tstart:Time, tend:Time) -> List[User]:
        departure = list()
        while tstart <= self._current_user.departure_time < tend:
            departure.append(self._current_user)
            try:
                self._current_user = self.construct_user(next(self._reader))
            except StopIteration:
                return departure
        return departure

    @staticmethod
    def construct_user(row):
        return User(row[0], row[2], row[3], Time(row[1]))

    def __del__(self):
        self._file.close()