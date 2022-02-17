from abc import ABC, abstractmethod
import csv
from typing import List

from mnms.tools.time import Time


class Observer(ABC):
    @abstractmethod
    def update(self, subject:'Subject'):
        pass


class TimeDependentObserver(ABC):
    @abstractmethod
    def update(self, subject:'TimeDependentSubject', time:Time):
        pass


class Subject(ABC):
    def __init__(self):
        self._observers: List[Observer] = []

    def attach(self, obs):
        self._observers.append(obs)

    def detach(self, obs):
        self._observers.remove(obs)

    def notify(self):
        for obs in self._observers:
            obs.update(self)


class TimeDependentSubject(ABC):
    def __init__(self):
        self._observers: List[TimeDependentObserver] = []

    def attach(self, obs):
        self._observers.append(obs)

    def detach(self, obs):
        self._observers.remove(obs)

    def notify(self, time:Time):
        for obs in self._observers:
            obs.update(self, time)


class CSVUserObserver(Observer):
    def __init__(self, filename: str):
        self._header = ["ID", "ORIGIN", "DESTINATION", "DEPARTURE_TIME", "ARRIVAL_TIME", "PATH", "COST_PATH"]
        self._filename = filename
        self._file = open(self._filename, "w")
        self._csvhandler = csv.writer(self._file, delimiter=';', quotechar='|')
        self._csvhandler.writerow(self._header)

    def __del__(self):
        self._file.close()

    def update(self, subject: 'User'):
        row = [subject.id,
               subject.origin,
               subject.destination,
               subject.departure_time,
               subject.arrival_time,
               ' '.join(subject.path) if subject.path is not None else None,
               subject.path_cost]
        self._csvhandler.writerow(row)


class CSVVehicleObserver(TimeDependentObserver):
    def __init__(self, filename: str):
        self._header = ["TIME", "ID", "LINK", "REMAINING LENGTH", "PASSENGERS"]
        self._filename = filename
        self._file = open(self._filename, "w")
        self._csvhandler = csv.writer(self._file, delimiter=';', quotechar='|')
        self._csvhandler.writerow(self._header)

    def __del__(self):
        self._file.close()

    def update(self, subject: 'Vehicle', time:Time):
        row = [str(time),
               subject.id,
               subject.current_link,
               subject.remaining_link_length,
               ' '.join(p for p in subject._passenger)]
        self._csvhandler.writerow(row)
