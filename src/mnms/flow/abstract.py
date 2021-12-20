from abc import ABC, abstractmethod
from typing import List

from mnms.tools.time import Time
from mnms.demand.user import User


class AbstractFlowMotor(ABC):
    def __init__(self):
        self._graph = None
        self._demand = list()
        self._tcurrent: Time = Time()

    def set_graph(self, mmgraph: "MultiModalGraph"):
        self._graph = mmgraph

    def set_initial_demand(self, demand:List[List]):
        self._demand = demand

    def run(self, tstart:str, tend:str, dt:float):
        self.initialize()
        tend = Time(tend)
        self._tcurrent = Time(tstart)
        while self._tcurrent < tend:
            self.update_time(dt)
            self.step(dt)
        self.finalize()

    def set_time(self, time:str):
        self._tcurrent = Time(time)

    @property
    def time(self):
        return self._tcurrent.time

    def update_time(self, dt):
        # print(dt)
        self._tcurrent = self._tcurrent.add_time(seconds=dt)
        # print(self._tcurrent)

    @abstractmethod
    def step(self, dt:float, new_users:List[User]):
        pass

    def initialize(self):
        pass

    def finalize(self):
        pass

    @abstractmethod
    def update_graph(self):
        pass