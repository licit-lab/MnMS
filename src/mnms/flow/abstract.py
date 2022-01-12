from abc import ABC, abstractmethod
from typing import List
import csv

from mnms.tools.time import Time, Dt
from mnms.demand.user import User


class AbstractFlowMotor(ABC):
    def __init__(self, outfile:str=None):
        self._graph = None
        self._demand = list()
        self._tcurrent: Time = Time()

        if outfile is None:
            self._write = False
        else:
            self._write = True
            self._outfile = open(outfile, "w")
            self._csvhandler = csv.writer(self._outfile, delimiter=';', quotechar='|')

    def set_graph(self, mmgraph: "MultiModalGraph"):
        self._graph = mmgraph

    def set_initial_demand(self, demand:List[List]):
        self._demand = demand

    def run(self, tstart:str, tend:str, dt:float):
        self.initialize()
        tend = Time(tend)
        self._tcurrent = Time(tstart)
        step = 0
        while self._tcurrent < tend:
            self.update_time(dt)
            self.step(dt)
            if self._write:
                self.write_result(step)
            step += 1
        self.finalize()

    def set_time(self, time:Time):
        self._tcurrent = time

    @property
    def time(self):
        return self._tcurrent.time

    def update_time(self, dt:Dt):
        self._tcurrent = self._tcurrent.add_time(dt)

    @abstractmethod
    def step(self, dt:float, new_users:List[User]):
        pass

    @abstractmethod
    def update_graph(self):
        pass

    def write_result(self, step_affectation:int, step_flow:int):
        raise NotImplementedError(f"{self.__class__.__name__} do not implement a write_result method")

    def initialize(self):
        pass

    def finalize(self):
        if self._write:
            self._outfile.close()

