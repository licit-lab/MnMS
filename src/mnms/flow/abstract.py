from abc import ABC, abstractmethod
from collections import defaultdict
from typing import List, Dict, Optional, Callable
import csv

from mnms.graph.zone import Zone
from mnms.time import Time, Dt
from mnms.graph.layers import MultiLayerGraph

class AbstractReservoir(ABC):
    def __init__(self, zone: Zone, modes: List[str]):
        """
        Abstract Reservoir class defining the interface for a MFD reservoir

        Args:
            zone: The zone object associated to the Reservoir
            modes: The modes in the Reservoir
        """
        self.id: str = zone.id
        self.zone = zone
        self.modes = modes
        self.dict_accumulations = defaultdict(lambda: 0)
        self.dict_speeds = defaultdict(lambda: 0.)

        self.ghost_accumulation: Callable[[Time], Dict[str, float]] = lambda x: {}

        self.trip_lengths = {}

    @abstractmethod
    def update_accumulations(self, dict_accumulations: Dict[str, int]):
        """
        Method updating the accumulation inside the Reservoir

        Args:
            dict_accumulations: The new accumulation

        Returns
        -------

        """
        pass

    @abstractmethod
    def update_speeds(self):
        """
        Method updating the speed inside the Reservoir

        Returns
        -------

        """
        pass

    def set_ghost_accumulation(self, f_acc: Callable[[Time], Dict[str, float]]):
        self.ghost_accumulation = f_acc

    def add_trip_length(self, l, mode):
        """Method that registers a new trip length in this reservoir.

        Args:
            -l: the trip length
            -mode: the vehicle type that achieved this trip
        """
        if mode in self.trip_lengths:
            self.trip_lengths[mode].append(l)
        else:
            self.trip_lengths[mode] = [l]

    def flush_trip_lengths(self):
        """Method that clean all trip lengths registered in this reservoir.
        """
        self.trip_lengths = {}

class AbstractMFDFlowMotor(ABC):
    def __init__(self, outfile:str=None):
        """Abstraction of a flow motor, two methods must be overridden `step` and `update_graph`.
        `step` define the core of the motor, i.e. the way `Vehicle` move. `update_graph` must update the cost of the graph.

        Args:
            outfile: If not `None` store the `User` position at each `step`
        """
        self._graph: MultiLayerGraph = None

        self._tcurrent: Time = Time()

        if outfile is None:
            self._write = False
        else:
            self._write = True
            self._outfile = open(outfile, "w")
            self._csvhandler = csv.writer(self._outfile, delimiter=';', quotechar='|')

    def set_graph(self, mlgraph: MultiLayerGraph):
        self._graph = mlgraph

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
    def update_graph(self, threshold):
        pass

    def write_result(self, step_affectation:int, step_flow:int):
        raise NotImplementedError(f"{self.__class__.__name__} do not implement a write_result method")

    def initialize(self):
        pass

    def add_reservoir(self, res: AbstractReservoir):
        pass

    def finalize(self):
        if self._write:
            self._outfile.close()
