from abc import ABC, abstractmethod
from typing import List

from mnms.tools.time import Time


class AbstractFlowMotor(ABC):
    def __init__(self):
        self._graph = None
        self._demand = list()
        self._tcurrent = None

    def set_graph(self, mmgraph: "MultiModalGraph"):
        self._graph = mmgraph

    def set_inital_demand(self, demand:List[List]):
        self._demand = demand

    def run(self, tstart:str, tend:str, dt:float):
        self.initialize()
        tend = Time(tend)
        self._tcurrent = Time(tstart)
        while self._tcurrent < tend:
            self.update_time(dt)
            self.step(dt)
        self.finalize()

    def update_time(self, dt):
        self._tcurrent = self._tcurrent.add_time(seconds=dt)

    @abstractmethod
    def step(self, dt:float):
        pass

    def initialize(self):
        pass

    def finalize(self):
        pass