from abc import ABC, abstractmethod
from typing import List

from mnms.demand import User
from mnms.demand.manager import AbstractDemandManager
from mnms.time import Dt, Time


class AbstractDemandHorizon(ABC):
    def __init__(self, manager: AbstractDemandManager, dt: Dt):
        """
        Abstraction of the demand horizon, it provides the next demand for the current time until current time + dt

        Args:
            manager: The demand manager
            dt: The time window of the horizon

        """
        self.dt: Dt = dt
        self.manager: AbstractDemandManager = manager.copy()

    @abstractmethod
    def get(self, tstart: Time) -> List[User]:
        """
        Return a list of User from tsart to start + dt

        Args:
            tstart: the start time of the horizon

        Returns:
            A list of Users

        """
        pass


class DemandHorizon(AbstractDemandHorizon):
    """
    A simple implementation of the Demand Horizon that returns the exact demand
    between tstart and tstart + dt
    """
    def get(self, tstart: Time):
        return self.manager.get_next_departures(tstart, tstart.add_time(self.dt))
