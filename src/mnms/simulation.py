from math import ceil
from time import time
import csv
import traceback
import random
from typing import List, Optional

import numpy as np

from mnms.demand import User
from mnms.graph.dynamic_space_sharing import DynamicSpaceSharing
from mnms.graph.layers import MultiLayerGraph
from mnms.flow.abstract import AbstractMFDFlowMotor
from mnms.flow.user_flow import UserFlow
from mnms.demand.manager import AbstractDemandManager
from mnms.travel_decision.abstract import AbstractDecisionModel
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import Time, Dt
from mnms.log import create_logger, attach_log_file, LOGLEVEL
from mnms.tools.progress import ProgressBar
from mnms.vehicles.manager import VehicleManager

log = create_logger(__name__)


class Supervisor(object):
    def __init__(self,
                 graph: MultiLayerGraph,
                 demand: AbstractDemandManager,
                 flow_motor: AbstractMFDFlowMotor,
                 decision_model: AbstractDecisionModel,
                 outfile: Optional[str] = None,
                 logfile: Optional[str] = None,
                 loglevel: LOGLEVEL = LOGLEVEL.WARNING):
        """
        Main class to launch a simulation

        Args:
            graph: The multi layer graph
            demand: The demand manager
            flow_motor: The flow motor
            decision_model: The decision model
            outfile: If not None write in the outfile at each time step the cost of each link in the multi layer graph
        """

        self._mlgraph: MultiLayerGraph = None
        self._demand: AbstractDemandManager = demand
        self._flow_motor: AbstractMFDFlowMotor = flow_motor

        self._decision_model:AbstractDecisionModel = decision_model
        self._user_flow: UserFlow = UserFlow()

        self.add_graph(graph)
        self._flow_motor.set_graph(graph)
        self._user_flow.set_graph(graph)

        self.tcurrent: Optional[Time] = None

        if outfile is None:
            self._write = False
        else:
            self._write = True
            self._outfile = open(outfile, "w")
            self._csvhandler = csv.writer(self._outfile, delimiter=';', quotechar='|')
            self._csvhandler.writerow(['AFFECTATION_STEP', 'TIME', 'ID', 'MOBILITY_SERVICE', 'TRAVEL_TIME'])

        if logfile is not None:
            attach_log_file(logfile, loglevel)

    def set_random_seed(self, seed):
        random.seed(seed)
        np.random.seed(seed)

    def add_graph(self, mmgraph: MultiLayerGraph):
        self._mlgraph = mmgraph
        self._mlgraph.construct_layer_service_mapping()
        for layer in mmgraph.layers.values():
            layer.initialize()

    def add_flow_motor(self, flow: AbstractMFDFlowMotor):
        self._flow_motor = flow
        flow.set_graph(self._mlgraph)

    def add_demand(self, demand: AbstractDemandManager):
        self._demand = demand

    def add_decision_model(self, model: AbstractDecisionModel):
        self._decision_model = model

    def get_new_users(self, principal_dt):
        log.info(f'Getting next departures {self.tcurrent}->{self.tcurrent.add_time(principal_dt)} ..')
        new_users = self._demand.get_next_departures(self.tcurrent, self.tcurrent.add_time(principal_dt))
        self._demand.construct_user_parameters(new_users)
        log.info(f'Done, {len(new_users)} new departure')

        return new_users

    def compute_user_paths(self, new_users: List[User]):
        log.info('Computing paths for new users ..')
        start = time()
        self._decision_model(new_users, self.tcurrent)
        end = time()
        log.info(f'Done [{end - start:.5} s]')

    def initialize(self, tstart:Time):
        for layer in self._mlgraph.layers.values():
            for service in layer.mobility_services.values():
                service.set_time(tstart)

        self._flow_motor.set_time(tstart)
        self._flow_motor.initialize(self._user_flow._walk_speed)

        self._user_flow.set_time(tstart)

        self._mlgraph.dynamic_space_sharing.cost = self._decision_model._cost

    def update_mobility_services(self, flow_dt:Dt):
        for layer in self._mlgraph.layers.values():
            for mservice in layer.mobility_services.values():
                log.info(f' Update mobility service {mservice.id}')
                mservice.update(flow_dt)
                mservice.update_time(flow_dt)

    def step_flow(self, flow_dt, users_step):
        log.info(' Step user flow ..')
        start = time()
        user_reach_dt_answer = self._user_flow.step(flow_dt, users_step)
        self._user_flow.update_time(flow_dt)
        end = time()
        log.info(f' Done [{end - start:.5} s]')

        self.step_dynamic_space_sharing()

        log.info(f' Perform matching for mobility services ...')
        start = time()
        user_reach_dt_pickup = list()
        for layer in self._mlgraph.layers.values():
            for ms in layer.mobility_services.values():
                user_refuse_service = ms.launch_matching()
                user_reach_dt_pickup.extend(user_refuse_service)

        all_refused_user = user_reach_dt_pickup + user_reach_dt_answer
        self._decision_model.set_refused_users(all_refused_user)
        for u in all_refused_user:
            self._user_flow.users.pop(u.id, None)
            self._user_flow._waiting_answer.pop(u.id, None)
        end = time()
        log.info(f' Done [{end - start:.5} s]')

        log.info(' Step MFD flow ..')
        start = time()
        self._flow_motor.step(flow_dt)
        self._flow_motor.update_time(flow_dt)
        end = time()
        log.info(f' Done [{end - start:.5} s]')

    def step_dynamic_space_sharing(self):
        veh_to_reroute = self._mlgraph.dynamic_space_sharing.update(self.tcurrent,
                                                                    list(VehicleManager._vehicles.values()))
        for veh, activity in veh_to_reroute:
            origin = activity.path[0][0][0]
            dest = activity.path[-1][0][1]
            mservice_id = veh.mobility_service

            layer = self._mlgraph.mapping_layer_services[mservice_id]
            new_path, _ = self._decision_model.compute_path(origin,
                                                            dest,
                                                            {layer.id},
                                                            {layer.id: mservice_id})

            if new_path:
                mservice = layer.mobility_services[mservice_id]
                new_veh_path = mservice.construct_veh_path(new_path)

                if activity is veh.activity:
                    for i, (old_link, new_link) in enumerate(zip(activity.path, new_veh_path)):
                        if old_link != new_link:
                            new_veh_path = new_veh_path[i:]
                            break

                activity.modify_path(new_veh_path)

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

        progress = ProgressBar(ceil((tend-tstart).to_seconds()/(flow_dt.to_seconds()*affectation_factor)))
        while self.tcurrent < tend:
            progress.update()
            progress.show()
            log.info(f'Current time: {self.tcurrent}, affectation step: {affectation_step}')

            new_users = self.get_new_users(principal_dt)

            # Set pickup_dt to infinite for all PT mobility services
            all_mob_services = [list(v.mobility_services.values()) for v in self._mlgraph.layers.values()]
            all_mob_services = [item for sublist in all_mob_services for item in sublist]
            pt_mob_services_names = set([ms.id for ms in all_mob_services if isinstance(ms,PublicTransportMobilityService)])
            for user in new_users:
                for pt_ms in pt_mob_services_names:
                    user.pickup_dt[pt_ms] = Dt(hours=24)

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
                    for mservice, costs in link.costs.items():
                        self._csvhandler.writerow([str(affectation_step), t_str, link.id, mservice, costs['travel_time']])
                end = time()
                log.info(f'Done [{end - start:.5} s]')

            log.info('-'*50)
            affectation_step += 1

        self._flow_motor.finalize()

        if self._decision_model._write:
            self._decision_model._outfile.close()

        if self._write:
            self._outfile.close()

        for obs in self._demand._observers:
            obs.finish()

        for layer in self._mlgraph.layers.values():
            for mservice in layer.mobility_services.values():
                if mservice._observer is not None:
                    mservice._observer.finish()

        progress.update()
        progress.show()
        progress.end()

    def create_crash_report(self, affectation_step, flow_step) -> dict:
        data = dict(time=str(self.tcurrent),
                    affectation_step=affectation_step,
                    flow_step=flow_step,
                    error=traceback.format_exc())

        return data
