from abc import ABC, abstractmethod
import csv
from typing import List

from mnms.tools.time import Time
from mnms.log import create_logger

log = create_logger(__name__)

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


class CSVUserObserver(TimeDependentObserver):
    def __init__(self, filename: str, prec:int=3):
        self._header = ["TIME", "ID", "LINK", "POSITION", "VEHICLE"]
        self._filename = filename
        self._file = open(self._filename, "w")
        self._csvhandler = csv.writer(self._file, delimiter=';', quotechar='|')
        self._csvhandler.writerow(self._header)
        self._prec = prec

    def __del__(self):
        self._file.close()

    def update(self, subject: 'User', time: Time):
        log.info(f"OBS {time}")
        row = [str(time),
               subject.id,
               f"{subject._current_link[0]} {subject._current_link[1]}",
               f"{subject.position[0]:.{self._prec}f} {subject.position[1]:.{self._prec}f}" if subject.position is not None else None,
               subject._vehicle]
        self._csvhandler.writerow(row)


class CSVVehicleObserver(TimeDependentObserver):
    def __init__(self, filename: str, prec:int=3):
        self._header = ["TIME", "ID", "TYPE", "LINK", "POSITION", "SPEED", "PASSENGERS"]
        self._filename = filename
        self._file = open(self._filename, "w")
        self._csvhandler = csv.writer(self._file, delimiter=';', quotechar='|')
        self._csvhandler.writerow(self._header)
        self._prec = prec

    def __del__(self):
        self._file.close()

    def update(self, subject: 'Vehicle', time:Time):
        row = [str(time),
               subject.id,
               subject.type,
               f"{subject.current_link[0]} {subject.current_link[1]}",
               f"{subject.position[0]:.{self._prec}f} {subject.position[1]:.{self._prec}f}" if subject.position is not None else None,
               f"{subject.speed:.{self._prec}f}" if subject.speed is not None else None,
               ' '.join(p for p in subject._passenger)]
        self._csvhandler.writerow(row)
