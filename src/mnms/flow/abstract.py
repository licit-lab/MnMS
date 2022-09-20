from abc import ABC, abstractmethod
from typing import List
import csv

from mnms.time import Time, Dt
from mnms.graph.layers import MultiLayerGraph


class AbstractFlowMotor(ABC):
    """Abstraction of a flow motor, two methods must be overridden `step` and `update_graph`.
    `step` define the core of the motor, i.e. the way `Vehicle` move. `update_graph` must update the cost of the graph.

    Parameters
    ----------
    outfile: str
        If not `None` store the `User` position at each `step`
    """
    def __init__(self, outfile:str=None):
        self._graph: MultiLayerGraph = None
        self._mobility_nodes = None
        self._flow_nodes = None

        self._demand = dict()
        self._tcurrent: Time = Time()

        if outfile is None:
            self._write = False
        else:
            self._write = True
            self._outfile = open(outfile, "w")
            self._csvhandler = csv.writer(self._outfile, delimiter=';', quotechar='|')

    def set_graph(self, mlgraph: MultiLayerGraph):
        self._graph = mlgraph

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
        self._tcurrent = time.copy()

    @property
    def time(self):
        return self._tcurrent.time

    def update_time(self, dt:Dt):
        self._tcurrent = self._tcurrent.add_time(dt)

    @abstractmethod
    def step(self, dt:float):
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

