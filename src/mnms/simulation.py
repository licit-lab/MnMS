import configparser
from time import time

from mnms.tools.io import load_graph
from mnms.graph.core import MultiModalGraph
from mnms.flow.abstract import AbstractFlowMotor
from mnms.demand.manager import DemandManager
from mnms.tools.time import Time
from mnms.graph.algorithms import compute_shortest_path
from mnms.log import rootlogger


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

    def update_graph_cost(self, nstep:int):
        self._update_graph = nstep

    def run(self, tstart: Time, tend: Time, dt_hour=0, dt_minute=0, dt_seconds=0):
        rootlogger.info(f'Start run from {tstart} to {tend}')
        tcurrent = tstart
        step = 0
        dt = Time.fromFloats(dt_hour, dt_minute, dt_seconds)

        self._flow_motor.set_time(tcurrent)
        self._flow_motor.initialize()

        while tcurrent < tend:
            rootlogger.info(f'Current time: {tcurrent}, step: {step}')
            rootlogger.info('Getting next departures ..')
            new_users = self._demand.get_next_departure(tcurrent, tcurrent.add_time(dt_hour, dt_minute, dt_seconds))
            rootlogger.info(f'Done, {len(new_users)} new departure')

            rootlogger.info('Computing new paths ..')
            start = time()
            [compute_shortest_path(self._graph, nu,
                                   cost='time',
                                   algorithm=self._shortest_path,
                                   heuristic=self._heuristic) for nu in new_users]
            end = time()
            rootlogger.info(f'Done [{end-start:.5} s]')

            rootlogger.info(f'Step of {self._flow_motor.__class__.__name__} ...')
            start = time()
            self._flow_motor.update_time(dt_hour, dt_minute, dt_seconds)
            self._flow_motor.step(dt.to_seconds(), new_users)
            end = time()
            rootlogger.info(f'Done [{end-start:.5} s]')

            if step % self._update_graph == 0:
                rootlogger.info('Updating graph ...')
                start = time()
                self._flow_motor.update_graph()
                end = time()
                rootlogger.info(f'Done [{end-start:.5} s]')

            tcurrent = tcurrent.add_time(dt_hour, dt_minute, dt_seconds)
            step += 1