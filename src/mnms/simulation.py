import configparser
from time import time

from mnms.tools.io import load_graph
from mnms.graph.core import MultiModalGraph
from mnms.flow.abstract import AbstractFlowMotor
from mnms.demand.manager import BaseDemandManager
from mnms.tools.time import Time, Dt
from mnms.graph.algorithms import compute_shortest_path_nodes
from mnms.log import rootlogger
from mnms.tools.exceptions import PathNotFound


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

    def add_demand(self, demand: BaseDemandManager):
        self._demand = demand

    def update_graph_cost(self, nstep:int):
        self._update_graph = nstep

    def run(self, tstart: Time, tend: Time, flow_dt: Dt, affectation_factor:int):
        rootlogger.info(f'Start run from {tstart} to {tend}')
        tcurrent = tstart
        step = 0
        principal_dt = flow_dt * affectation_factor

        self._flow_motor.set_time(tcurrent)
        self._flow_motor.initialize()

        while tcurrent < tend:
            rootlogger.info(f'Current time: {tcurrent}, step: {step}')

            rootlogger.info(f'Getting next departures {tcurrent}->{tcurrent.add_time(principal_dt)} ..')
            new_users = self._demand.get_next_departures(tcurrent, tcurrent.add_time(principal_dt))
            iter_new_users = iter(new_users)
            rootlogger.info(f'Done, {len(new_users)} new departure')

            rootlogger.info('Computing paths for new users ..')
            start = time()

            #TODO: shortest path computation will be in TravelDecision module
            for nu in new_users:
                try:
                    compute_shortest_path_nodes(self._graph, nu, cost='time', algorithm=self._shortest_path,
                                                heuristic=self._heuristic)
                except PathNotFound:
                    rootlogger.warning(f"Path not found for {nu}")

            end = time()
            rootlogger.info(f'Done [{end-start:.5} s]')

            rootlogger.info(f'Launching {affectation_factor} step of {self._flow_motor.__class__.__name__} ...')
            start = time()
            if len(new_users) > 0:
                u = next(iter_new_users)
                for _ in range(affectation_factor):
                    next_time = tcurrent.add_time(flow_dt)
                    users_step = list()
                    try:
                        while tcurrent <= u.departure_time < next_time:
                            users_step.append(u)
                            u = next(iter_new_users)
                    except StopIteration:
                        pass
                    self._flow_motor.update_time(flow_dt)
                    self._flow_motor.step(flow_dt.to_seconds(), users_step)
                    tcurrent = next_time

            else:
                for _ in range(affectation_factor):
                    next_time = tcurrent.add_time(flow_dt)
                    self._flow_motor.update_time(flow_dt)
                    self._flow_motor.step(flow_dt.to_seconds(), [])
                    tcurrent = next_time
            end = time()
            rootlogger.info(f'Done [{end-start:.5} s]')

            rootlogger.info('Updating graph ...')
            start = time()
            self._flow_motor.update_graph()
            end = time()
            rootlogger.info(f'Done [{end-start:.5} s]')
            rootlogger.info('-'*50)
            step += 1