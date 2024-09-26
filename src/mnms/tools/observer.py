from abc import ABC, abstractmethod
import csv
from typing import List

from mnms.time import Time
from mnms.log import create_logger

log = create_logger(__name__)


class Observer(ABC):
    """
                Represents a observer
    """
    @abstractmethod
    def update(self, subject:'Subject'):
        pass

    @abstractmethod
    def finish(self):
        pass


class TimeDependentObserver(ABC):
    """
                    Represents a time dependant observer
    """
    @abstractmethod
    def update(self, subject:'TimeDependentSubject', time:Time):
        pass

    @abstractmethod
    def finish(self):
        pass


class Subject(ABC):
    """
            Represents what is being observed
    """

    def __init__(self):
        """Create an empty observer list"""
        self._observers: List[Observer] = []

    def attach(self, obs):
        """If the observer is not in the list,
        append it into the list"""
        if obs not in self._observers:
            self._observers.append(obs)

    def detach(self, obs):
        """Remove the observer from the observer list"""
        self._observers.remove(obs)

    def notify(self):
        """Alerts the observers"""
        for obs in self._observers:
            obs.update(self)


class TimeDependentSubject(ABC):
    """
        Represents time-dependent observations
    """

    def __init__(self):
        """Create an empty observer list"""
        self._observers: List[TimeDependentObserver] = []

    def attach(self, obs):
        """If the observer is not in the list,
        append it into the list"""
        if obs not in self._observers:
            self._observers.append(obs)

    def detach(self, obs):
        """Remove the observer from the observer list"""
        self._observers.remove(obs)

    def notify(self, time: Time):
        """Alerts the observers"""
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
        self._header = ["TIME", "ID", "LINK", "POSITION", "DISTANCE", "STATE", "VEHICLE"]
        self._filename = filename
        self._file = open(self._filename, "w")
        self._csvhandler = csv.writer(self._file, delimiter=';', quotechar='|')
        self._csvhandler.writerow(self._header)
        self._prec = prec

    def finish(self):
        self._file.close()

    def update(self, subject: 'User', t: Time):
        row = [t.time,
               subject.id,
               f"{subject.current_link[0]} {subject.current_link[1]}" if subject.current_link is not None else None,
               f"{subject.position[0]:.{self._prec}f} {subject.position[1]:.{self._prec}f}" if subject.position is not None else None,
               f"{subject.distance:.{self._prec}f}",
               subject.state.name,
               str(subject.vehicle.id) if subject.vehicle is not None else None]
        # log.info(f"OBS {time}: {row}")

        self._csvhandler.writerow(row)


class CSVVehicleObserver(TimeDependentObserver):
    def __init__(self, filename: str, prec:int=3):
        """
        Observer class to write information about vehicles during a simulation

        Args:
            filename: The name of the file
            prec: The precision for floating point number
        """
        self._header = ["TIME", "ID", "TYPE", "LINK", "POSITION", "SPEED", "STATE", "DISTANCE", "PASSENGERS", "TRAVELED_NODES"]
        self._filename = filename
        self._file = open(self._filename, "w")
        self._csvhandler = csv.writer(self._file, delimiter=';', quotechar='|')
        self._csvhandler.writerow(self._header)
        self._prec = prec


    def finish(self):
        self._file.close()

    def update(self, subject: 'Vehicle', t:Time):
        row = [t.time,
               subject.id,
               subject.type,
               f"{subject.current_link[0]} {subject.current_link[1]}" if subject.current_link is not None else None,
               f"{subject.position[0]:.{self._prec}f} {subject.position[1]:.{self._prec}f}" if subject.position is not None else None,
               f"{subject.speed:.{self._prec}f}" if subject.speed is not None else None,
               subject.activity_type.name if subject.activity_type is not None else None,
               f"{subject.distance:.{self._prec}f}",
               ' '.join(p for p in subject.passengers),
               ' '.join(subject._achieved_path_since_last_notify)]
        subject.flush_achieved_path_since_last_notify()
        # log.info(f"OBS {time}: {row}")
        self._csvhandler.writerow(row)
