from time import time
import csv
import traceback
import random
from typing import List

import numpy as np

from mnms.demand import User
from mnms.graph.layers import MultiLayerGraph
from mnms.flow.abstract import AbstractFlowMotor
from mnms.flow.user_flow import UserFlow
from mnms.demand.manager import AbstractDemandManager
from mnms.travel_decision.abstract import AbstractDecisionModel
from mnms.time import Time, Dt
from mnms.log import create_logger
from mnms.tools.exceptions import PathNotFound

log = create_logger(__name__)


class Supervisor(object):
    def __init__(self,
                 graph: MultiLayerGraph,
                 demand: AbstractDemandManager,
                 flow_motor: AbstractFlowMotor,
                 decision_model: AbstractDecisionModel,
                 outfile: str = None):

        self._mlgraph: MultiLayerGraph = None
        self._demand: AbstractDemandManager = demand
        self._flow_motor: AbstractFlowMotor = flow_motor

        self._decision_model:AbstractDecisionModel = decision_model
        self._user_flow = UserFlow()

        self.add_graph(graph)
        self._flow_motor.set_graph(graph)
        self._user_flow.set_graph(graph)

        
        self.tcurrent = None

        if outfile is None:
            self._write = False
        else:
            self._write = True
            self._outfile = open(outfile, "w")
            self._csvhandler = csv.writer(self._outfile, delimiter=';', quotechar='|')
            self._csvhandler.writerow(['AFFECTATION_STEP', 'TIME', 'ID', 'TRAVEL_TIME'])

    def set_random_seed(self, seed):
        random.seed(seed)
        np.random.seed(seed)

    def add_graph(self, mmgraph: MultiLayerGraph):
        self._mlgraph = mmgraph
        self._mlgraph.construct_layer_service_mapping()
        for layer in mmgraph.layers.values():
            layer.initialize()

    def add_flow_motor(self, flow: AbstractFlowMotor):
        self._flow_motor = flow
        flow.set_graph(self._mlgraph)

    def add_demand(self, demand: AbstractDemandManager):
        self._demand = demand

    def add_decision_model(self, model: AbstractDecisionModel):
        self._decision_model = model

    def get_new_users(self, principal_dt):
        log.info(f'Getting next departures {self.tcurrent}->{self.tcurrent.add_time(principal_dt)} ..')
        new_users = self._demand.get_next_departures(self.tcurrent, self.tcurrent.add_time(principal_dt))
        log.info(f'Done, {len(new_users)} new departure')

        return new_users

    def compute_user_paths(self, new_users: List[User]):
        log.info('Computing paths for new users ..')
        start = time()
        self._decision_model(new_users)
        end = time()
        log.info(f'Done [{end - start:.5} s]')
        
    def initialize(self, tstart:Time):

        for link in self._mlgraph.graph.links.values():
            if link.label == "TRANSIT":
                speed = self._user_flow._walk_speed
            else:
                speed = self._mlgraph.layers[link.label].default_speed

            link.update_costs({"speed": speed,
                              "travel_time": link.length/speed})

        for layer in self._mlgraph.layers.values():
            for service in layer.mobility_services.values():
                service.set_time(tstart)
        
        self._flow_motor.set_time(tstart)
        self._flow_motor.initialize()

        self._user_flow.set_time(tstart)

    def update_mobility_services(self, flow_dt:Dt):
        for layer in self._mlgraph.layers.values():
            for mservice in layer.mobility_services.values():
                log.info(f' Update mobility service {mservice.id}')
                mservice.update(flow_dt)
                mservice.update_time(flow_dt)
            
    def step_flow(self, flow_dt, users_step):
        # TO CHECK:in the right order ? (if the other direction, there is a time step difference between the moments of creation of the vehicles and the accumulation)
        log.info(' Step user flow ..')
        start = time()
        self._user_flow.update_time(flow_dt)
        self._user_flow.step(flow_dt, users_step)
        end = time()
        log.info(f' Done [{end - start:.5} s]')
        log.info(' Step MFD flow ..')
        start = time()
        self._flow_motor.update_time(flow_dt)
        self._flow_motor.step(flow_dt)
        end = time()
        log.info(f' Done [{end - start:.5} s]')

    def step(self, affectation_factor, affectation_step, flow_dt, flow_step, new_users):
        if len(new_users) > 0:
            iter_new_users = iter(new_users)
            u = next(iter_new_users)
            for _ in range(affectation_factor):
                next_time = self.tcurrent.add_time(flow_dt)
                users_step = list()
                try:
                    while self.tcurrent <= u.departure_time < next_time:
                        users_step.append(u)
                        u = next(iter_new_users)
                except StopIteration:
                    pass

                self.update_mobility_services(flow_dt)

                self.step_flow(flow_dt, users_step)
                if self._flow_motor._write:
                    self._flow_motor.write_result(affectation_step, flow_step)
                self.tcurrent = next_time
                flow_step += 1

        else:
            for _ in range(affectation_factor):
                next_time = self.tcurrent.add_time(flow_dt)
                self.update_mobility_services(flow_dt)
                self.step_flow(flow_dt, [])
                if self._flow_motor._write:
                    self._flow_motor.write_result(affectation_step, flow_step)
                self.tcurrent = next_time
                flow_step += 1

    def run(self, tstart: Time, tend: Time, flow_dt: Dt, affectation_factor:int):
        log.info(f'Start run from {tstart} to {tend}')
        
        self.initialize(tstart)

        affectation_step = 0
        flow_step = 0
        principal_dt = flow_dt * affectation_factor

        self.tcurrent = tstart

        while self.tcurrent < tend:
            # try:
            log.info(f'Current time: {self.tcurrent}, affectation step: {affectation_step}')

            new_users = self.get_new_users(principal_dt)

            self.compute_user_paths(new_users)

            log.info(f'Launching {affectation_factor} step of flow ...')
            start = time()
            self.step(affectation_factor, affectation_step, flow_dt, flow_step, new_users)
            end = time()
            log.info(f'Done [{end-start:.5} s]')

            log.info(' Updating graph ...')
            start = time()
            self._flow_motor.update_graph()
            end = time()
            log.info(f' Done [{end-start:.5} s]')

            if self._write:
                log.info('Writing travel time of each link in graph ...')
                start = time()
                t_str = self._flow_motor.time
                for link in self._mlgraph.graph.links.values():
                    self._csvhandler.writerow([str(affectation_step), t_str, link.id, link.costs['travel_time']])
                end = time()
                log.info(f'Done [{end - start:.5} s]')

            log.info('-'*50)
            affectation_step += 1
            # except Exception as e:
                # cwd = os.getcwd()
                # report_file = cwd+'/'+'report.json'
                # log.error(e)
                # log.error(f"Simulation failed at {self.tcurrent}, writing a report at {report_file}")
                # with open(report_file, 'w') as f:
                #     json.dump(self.create_crash_report(affectation_step, flow_step), f, indent=4)
                # sys.exit(-1)

        self._flow_motor.finalize()

        if self._decision_model._write:
            self._decision_model._outfile.close()

        if self._write:
            self._outfile.close()

    def create_crash_report(self, affectation_step, flow_step) -> dict:
        data = dict(time=str(self.tcurrent),
                    affectation_step=affectation_step,
                    flow_step=flow_step,
                    error=traceback.format_exc())

        return data

