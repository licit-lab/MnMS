import configparser
from time import time
import csv

from mnms.graph.core import MultiModalGraph
from mnms.flow.abstract import AbstractFlowMotor
from mnms.demand.manager import AbstractDemandManager
from mnms.travel_decision.model import DecisionModel
from mnms.tools.time import Time, Dt
from mnms.log import create_logger
from mnms.tools.exceptions import PathNotFound
from mnms.tools.progress import ProgressBar

log = create_logger(__name__)

class Supervisor(object):
    def __init__(self,
                 graph:MultiModalGraph=None,
                 demand:AbstractDemandManager=None,
                 flow_motor:AbstractFlowMotor=None,
                 decision_model:DecisionModel=None,
                 outfile:str=None):

        self._graph: MultiModalGraph = graph
        self._demand: AbstractDemandManager = demand
        self._flow_motor: AbstractFlowMotor = flow_motor
        self._decision_model:DecisionModel = decision_model

        if flow_motor is not None:
            flow_motor.set_graph(graph)

        if outfile is None:
            self._write = False
        else:
            self._write = True
            self._outfile = open(outfile, "w")
            self._csvhandler = csv.writer(self._outfile, delimiter=';', quotechar='|')
            self._csvhandler.writerow(['AFFECTATION_STEP', 'TIME', 'ID', 'TRAVEL_TIME'])

    def add_graph(self, mmgraph: MultiModalGraph):
        self._graph = mmgraph

    def add_flow_motor(self, flow: AbstractFlowMotor):
        self._flow_motor = flow
        flow.set_graph(self._graph)

    def add_demand(self, demand: AbstractDemandManager):
        self._demand = demand

    def add_decision_model(self, model: DecisionModel):
        self._decision_model = model

    def run(self, tstart: Time, tend: Time, flow_dt: Dt, affectation_factor:int):
        log.info(f'Start run from {tstart} to {tend}')
        tcurrent = tstart
        affectation_step = 0
        flow_step = 0
        principal_dt = flow_dt * affectation_factor

        self._flow_motor.set_time(tcurrent)
        self._flow_motor.initialize()

        while tcurrent < tend:
            log.info(f'Current time: {tcurrent}, affectation step: {affectation_step}')

            log.info(f'Getting next departures {tcurrent}->{tcurrent.add_time(principal_dt)} ..')
            new_users = self._demand.get_next_departures(tcurrent, tcurrent.add_time(principal_dt))
            iter_new_users = iter(new_users)
            log.info(f'Done, {len(new_users)} new departure')

            log.info('Computing paths for new users ..')
            start = time()

            # for nu in ProgressBar(new_users, "Compute paths"):
            for nu in new_users:
                try:
                    self._decision_model(nu)
                except PathNotFound:
                    pass

            end = time()
            log.info(f'Done [{end-start:.5} s]')

            log.info(f'Launching {affectation_factor} step of {self._flow_motor.__class__.__name__} ...')
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
                    if self._flow_motor._write:
                        self._flow_motor.write_result(affectation_step, flow_step)
                    tcurrent = next_time
                    flow_step += 1

            else:
                for _ in range(affectation_factor):
                    next_time = tcurrent.add_time(flow_dt)
                    self._flow_motor.update_time(flow_dt)
                    self._flow_motor.step(flow_dt.to_seconds(), [])
                    if self._flow_motor._write:
                        self._flow_motor.write_result(affectation_step, flow_step)
                    tcurrent = next_time
                    flow_step += 1
            end = time()
            log.info(f'Done [{end-start:.5} s]')

            log.info('Updating graph ...')
            start = time()
            self._flow_motor.update_graph()
            end = time()
            log.info(f'Done [{end-start:.5} s]')

            if self._write:
                log.info('Writing travel time of each link in graph ...')
                start = time()
                t_str = self._flow_motor.time
                for link in self._graph.mobility_graph.links.values():
                    self._csvhandler.writerow([str(affectation_step), t_str, link.id, link.costs['time']])
                end = time()
                log.info(f'Done [{end - start:.5} s]')

            log.info('-'*50)
            affectation_step += 1

        self._flow_motor.finalize()

        if self._decision_model._write:
            self._decision_model._outfile.close()

        if self._write:
            self._outfile.close()