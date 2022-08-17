from abc import ABC, abstractmethod

from mnms.demand.manager import AbstractDemandManager
from mnms.time import Dt, Time


class AbstractDemandHorizon(ABC):
    def __init__(self, manager: AbstractDemandManager, dt: Dt):
        """

        Parameters
        ----------
        manager
        dt
        """
        self.dt: Dt = dt
        self.manager: AbstractDemandManager = manager.copy()

    @abstractmethod
    def get(self, tstart: Time):
        pass


class DemandHorizon(AbstractDemandHorizon):
    def get(self, tstart: Time):
        return self.manager.get_next_departures(tstart, tstart.add_time(self.dt))
