from abc import ABC, abstractmethod
import csv
from typing import List, Dict


class Observer(ABC):
    @abstractmethod
    def update(self, **kwargs):
        pass


class Subject():
    def __init__(self):
        self._observers: List[Observer] = []

    def attach(self, obs):
        self._observers.append(obs)

    def detach(self, obs):
        self._observers.remove(obs)

    def notify(self):
        raise NotImplementedError


class CSVObserver(Observer):
    def __init__(self, filename: str, header:List[str]):
        self._header = header
        self._filename = filename
        self._file = open(self._filename, "w")
        self._csvhandler = csv.writer(self._file, delimiter=';', quotechar='|')
        self._csvhandler.writerow(header)

    def __del__(self):
        self._file.close()

    def update(self, **kwargs):
        row = [kwargs.get(key) for key in self._header]
        self._csvhandler.writerow(row)
