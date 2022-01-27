from abc import ABC, abstractmethod
import csv
from typing import List, Dict


class Observer(ABC):
    @abstractmethod
    def update(self, subject:'Subject'):
        pass


class Subject(ABC):
    def __init__(self):
        self._observers: List[Observer] = []

    def attach(self, obs):
        self._observers.append(obs)

    def detach(self, obs):
        self._observers.remove(obs)

    def notify(self):
        raise NotImplementedError


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
               subject.departure_time.time,
               subject.arrival_time.time,
               ' '.join(subject.path) if subject.path is not None else None,
               subject.path_cost]
        self._csvhandler.writerow(row)
