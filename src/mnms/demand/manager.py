import csv
import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Literal, Union

import numpy as np

from mnms.demand.user import User
from mnms.log import create_logger
from mnms.time import Time
from mnms.tools.exceptions import CSVDemandParseError
from mnms.tools.observer import Observer

log = create_logger(__name__)


class AbstractDemandManager(ABC):
    """Abstract class for loading a User demand
    """
    def __init__(self):
        self._observers = []
        self._user_to_attach = []


    @abstractmethod
    def get_next_departures(self, tstart:Time, tend: Time) -> List[User]:
        """Return the Users with a departure time between tstart and tend

        Parameters
        ----------
        tstart: Time
            Lower bound of departure time
        tend: Time
            Upper bound of departure time

        Returns
        -------
        List[User]

        """
        pass

    def add_user_observer(self, obs:Observer, user_ids:Union[Literal['all'], List[str]]="all"):
        self._observers.append(obs)
        self._user_to_attach.append(user_ids)


class BaseDemandManager(AbstractDemandManager):
    """Basic demand manager, it takes a list of User as input

    Parameters
    ----------
    users: List[User]
        list of User to manage
    """
    def __init__(self, users):
        super(BaseDemandManager, self).__init__()
        self._users = users
        self._iter_demand = iter(self._users)
        self._current_user = next(self._iter_demand)

        self.nb_users = len(self._users)

    def get_next_departures(self, tstart:Time, tend:Time) -> List[User]:
        departure = list()
        while tstart <= self._current_user.departure_time < tend:
            # Attaching observers to Users
            for iobs, obs in enumerate(self._observers):
                if self._user_to_attach[iobs] == 'all' or self._current_user.id in self._user_to_attach[iobs]:
                    self._current_user.attach(obs)

            departure.append(self._current_user)
            try:
                self._current_user = next(self._iter_demand)
            except StopIteration:
                return departure
        return departure

    def show_users(self):
        for u in self._users:
            print(u)

    def to_csv(self, file: Union[Path, str], delimiter=";"):
        with open(file, 'w') as f:
            writer = csv.writer(f, delimiter=delimiter)
            writer.writerow(["ID","DEPARTURE","ORIGIN","DESTINATION"])

            for u in self._users:
                writer.writerow([u.id, u.departure_time, u.origin, u.destination])


class CSVDemandManager(AbstractDemandManager):
    """Read a demand from a CSV file

    Parameters
    ----------
    csvfile: str
        Path to the CSV file
    demand_type: Literal[node, coordinate]
        Type of demand, either the origin?destination are node ids or coordinates
    delimiter: str
        Delimiter for the CSV file
    """
    def __init__(self, csvfile: Union[Path, str], delimiter=';'):
        super(CSVDemandManager, self).__init__()
        self._filename = csvfile
        self._file = open(self._filename, 'r')
        self._reader = csv.reader(self._file, delimiter=delimiter, quotechar='|')
        self._demand_type = None

        try:
            next(self._reader)
        except StopIteration:
            log.error(f'{self._filename} is empty')
            sys.exit(-1)

        first_line = next(self._reader)
        match_x=re.match(r'^[-+]?[0-9]*\.*[0-9]*\d\s[-+]?[0-9]*\.*[0-9]*\d$', first_line[2])
        match_y=re.match(r'^[-+]?[0-9]*\.*[0-9]*\d\s[-+]?[0-9]*\.*[0-9]*\d$', first_line[3])
        if match_x is not None and match_y is not None:
            self._demand_type = 'coordinate'
        else:
            match_x = re.match(r'^\w+$', first_line[2].strip())
            match_y = re.match(r'^\w+$', first_line[3].strip())
            if match_x is not None and match_y is not None:
                self._demand_type = 'node'
            else:
                raise CSVDemandParseError(csvfile)

        self._current_user = self.construct_user(first_line)

    def get_next_departures(self, tstart:Time, tend:Time) -> List[User]:
        departure = list()

        # If the lower bound of next departures is after the fist departure in the demand, we skip the first users until
        # reaching the  lower bound of next departures
        while self._current_user.departure_time < tstart:
            try:
                self._current_user = self.construct_user(next(self._reader))
            except StopIteration:
                return departure

        while tstart <= self._current_user.departure_time < tend:
            # Attaching observers to Users
            for iobs, obs in enumerate(self._observers):
                if self._user_to_attach[iobs] == 'all' or self._current_user.id in self._user_to_attach[iobs]:
                    self._current_user.attach(obs)

            departure.append(self._current_user)
            try:
                self._current_user = self.construct_user(next(self._reader))
            except StopIteration:
                return departure

        return departure

    def construct_user(self, row):
        if self._demand_type == 'node':
            origin = row[2]
            destination = row[3]
        elif self._demand_type == 'coordinate':
            origin = np.fromstring(row[2], sep=' ')
            destination = np.fromstring(row[3], sep=' ')
        else:
            raise TypeError(f"demand_type must be either 'node' or 'coordinate'")
        return User(row[0], origin, destination, Time(row[1]), available_mobility_services=None if len(row) == 4 else row[4].split(' '))

    def __del__(self):
        self._file.close()