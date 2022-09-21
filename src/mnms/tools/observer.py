from abc import ABC, abstractmethod
import csv
from typing import List

from mnms.time import Time
from mnms.log import create_logger

log = create_logger(__name__)


class Observer(ABC):
    @abstractmethod
    def update(self, subject:'Subject'):
        pass

    @abstractmethod
    def finish(self):
        pass


class TimeDependentObserver(ABC):
    @abstractmethod
    def update(self, subject:'TimeDependentSubject', time:Time):
        pass

    @abstractmethod
    def finish(self):
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

    def notify(self, time: Time):
        for obs in self._observers:
            obs.update(self, time)


class CSVUserObserver(TimeDependentObserver):
    def __init__(self, filename: str, prec:int=3):
        """
        Observer class to write information about users during a simulation

        Args:
            filename: The name of the file
            prec: The precision for floating point number
        """
        self._header = ["TIME", "ID", "LINK", "POSITION", "DISTANCE", "STATE", "VEHICLE", "CONTINUOUS_JOURNEY"]
        self._filename = filename
        self._file = open(self._filename, "w")
        self._csvhandler = csv.writer(self._file, delimiter=';', quotechar='|')
        self._csvhandler.writerow(self._header)
        self._prec = prec

    def finish(self):
        self._file.close()

    def update(self, subject: 'User', time: Time):
        row = [str(time),
               subject.id,
               f"{subject._current_link[0]} {subject._current_link[1]}",
               f"{subject.position[0]:.{self._prec}f} {subject.position[1]:.{self._prec}f}" if subject.position is not None else None,
               f"{subject.distance:.{self._prec}f}",
               subject.state.name,
               str(subject._vehicle.id) if subject._vehicle is not None else None,
               subject._continuous_journey]
        log.info(f"OBS {time}: {row}")

        self._csvhandler.writerow(row)


class CSVVehicleObserver(TimeDependentObserver):
    def __init__(self, filename: str, prec:int=3):
        """
        Observer class to write information about vehicles during a simulation

        Args:
            filename: The name of the file
            prec: The precision for floating point number
        """
        self._header = ["TIME", "ID", "TYPE", "LINK", "POSITION", "SPEED", "STATE", "DISTANCE", "PASSENGERS"]
        self._filename = filename
        self._file = open(self._filename, "w")
        self._csvhandler = csv.writer(self._file, delimiter=';', quotechar='|')
        self._csvhandler.writerow(self._header)
        self._prec = prec


    def finish(self):
        self._file.close()

    def update(self, subject: 'Vehicle', time:Time):
        row = [str(time),
               subject.id,
               subject.type,
               f"{subject.current_link[0]} {subject.current_link[1]}" if subject.current_link is not None else None,
               f"{subject.position[0]:.{self._prec}f} {subject.position[1]:.{self._prec}f}" if subject.position is not None else None,
               f"{subject.speed:.{self._prec}f}",
               subject.state.name if subject.state is not None else None,
               f"{subject.distance:.{self._prec}f}",
               ' '.join(p for p in subject.passenger)]
        log.info(f"OBS {time}: {row}")
        self._csvhandler.writerow(row)
