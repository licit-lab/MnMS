import configparser

from mnms.tools.io import load_graph
from mnms.graph.core import MultiModalGraph
from mnms.flow.abstract import AbstractFlowMotor
from mnms.demand.manager import DemandManager
from mnms.tools.time import Time
from mnms.graph.algorithms import compute_shortest_path


class Supervisor(object):
    def __init__(self):
        self._graph: MultiModalGraph = None
        self._demand: DemandManager = None
        self._parameters = None
        self._flow_motor: AbstractFlowMotor = None
        self._update_graph = 1
        self._shortest_path = 'astar'
        self._heuristic = None

    def load_graph(self, file:str):
        self.graph = load_graph(file)

    def load_config(self, file:str):
        config = configparser.ConfigParser()
        config.read(file)

        self.load_graph(config['GRAPH']['PATH'])

    def add_graph(self, mmgraph: MultiModalGraph):
        self._graph = mmgraph

    def add_flow_motor(self, flow: AbstractFlowMotor):
        self._flow_motor = flow
        flow.set_graph(self._graph)

    def add_demand(self, demand: DemandManager):
        self._demand = demand

    def run(self, tstart: Time, tend: Time, dt_hour=0, dt_minute=0, dt_seconds=0):
        tcurrent = tstart
        step = 0
        dt = Time.fromFloats(dt_hour, dt_minute, dt_seconds)
        while tcurrent < tend:
            new_users = self._demand.get_next_departure(tcurrent, tcurrent.add_time(dt_hour, dt_minute, dt_seconds))
            for nu in new_users:
                new_users.path = compute_shortest_path(self._graph, nu.origin, nu.destination,
                                                       cost='time',
                                                       algorithm=self._shortest_path,
                                                       heuristic=self._heuristic)
            self._flow_motor.step(dt, new_users)
            if step % self._update_graph == 0:
                self._flow_motor.update_graph()

            tcurrent = tcurrent.add_time(dt_hour, dt_minute, dt_seconds)
            step += 1