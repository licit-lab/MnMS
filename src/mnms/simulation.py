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
from mnms.travel_decision.abstract import AbstractDecisionModel, Event
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import Time, Dt
from mnms.log import create_logger, attach_log_file, LOGLEVEL
from mnms.tools.progress import ProgressBar
from mnms.vehicles.manager import VehicleManager
from mnms.vehicles.veh_type import Vehicle

log = create_logger(__name__)


class Supervisor(object):
    def __init__(self,
                 graph: MultiLayerGraph,
                 demand: AbstractDemandManager,
                 flow_motor: AbstractMFDFlowMotor,
                 decision_model: AbstractDecisionModel,
                 user_flow: UserFlow = None,
                 outfile: Optional[str] = None,
                 logfile: Optional[str] = None,
                 loglevel: LOGLEVEL = LOGLEVEL.WARNING):
        """
        Main class to launch a simulation.

        Args:
            -graph: The multi layer graph
            -demand: The demand manager
            -flow_motor: The flow motor
            -decision_model: The decision model
            -user_flow: The user flow motor
            -outfile: If not None write in the outfile at each time step the cost
                      of each link in the multi layer graph
            -logfile: file where simulation log should be printed
            -loglevel: level of log to print
        """

        self._mlgraph: MultiLayerGraph = None
        self._demand: AbstractDemandManager = demand
        self._flow_motor: AbstractMFDFlowMotor = flow_motor

        self._decision_model:AbstractDecisionModel = decision_model
        if user_flow is None:
            self._user_flow: UserFlow = UserFlow()
        else:
            self._user_flow = user_flow
            
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
            self._csvhandler.writerow(['AFFECTATION_STEP', 'TIME', 'ID', 'MOBILITY_SERVICE', 'COSTS'])

        if logfile is not None:
            attach_log_file(logfile, loglevel)

    def set_random_seed(self, seed: int):
        """Method that sets the seed for all modules that can be stochastic.

        Args:
            -seed: seed as an integer
        """
        if seed is not None:
            # NB: For now, only the decision model can be stochastic
            self._decision_model.set_random_seed(seed)

    def add_graph(self, mlgraph: MultiLayerGraph):
        """Method to add a multilayer graph to the supervisor.
        A map associating each mobility service of the graph to the corresponding
        layer is build. Timetables of the PublicTransportLayer objects of the graph
        are initialized.

        Args:
            -mlgraph: the MultiLayerGraph object to add
        """
        self._mlgraph = mlgraph
        self._mlgraph.construct_layer_service_mapping()
        for layer in mlgraph.layers.values():
            layer.initialize()

    def add_flow_motor(self, flow: AbstractMFDFlowMotor):
        """Method to add a flow motor to the supervisor.

        Args:
            -flow: the AbstractMFDFlowMotor object to add
        """
        self._flow_motor = flow
        flow.set_graph(self._mlgraph)

    def add_demand(self, demand: AbstractDemandManager):
        """Method to add a demand manager to the supervisor.

        Args:
            -demand: the AbstractDemandManager object to add
        """
        self._demand = demand

    def add_decision_model(self, model: AbstractDecisionModel):
        """Method to add a decision model to the supervisor.

        Args:
            -model: the AbstractDecisionModel object to add
        """
        self._decision_model = model

    def initialize(self, tstart:Time):
        """Method that initializes the simulation by setting the time of the different
        modules  and initializing the costs on the multilayer graph of the simulation.

        Args:
            -tstart: start time of the simulation
        """
        for layer in self._mlgraph.layers.values():
            for service in layer.mobility_services.values():
                service.set_time(tstart)

        self._mlgraph.initialize_costs(self._user_flow._walk_speed)

        self._flow_motor.set_time(tstart)
        self._flow_motor.initialize()

        self._user_flow.set_time(tstart)

        self._mlgraph.dynamic_space_sharing.set_cost(self._decision_model._cost)

    def finalize(self):
        """Method that finalizes the simulation by closing open files, and cleaning
        class attributes.
        """
        self._flow_motor.finalize()

        self._user_flow.finalize()

        if self._decision_model._write:
            self._decision_model._outfile.close()

        if self._write:
            self._outfile.close()

        if self._demand:
            for obs in self._demand._observers:
                obs.finish()

        for layer in self._mlgraph.layers.values():
            for mservice in layer.mobility_services.values():
                if mservice._observer is not None:
                    mservice._observer.finish()

        # Clean the class attributes
        VehicleManager.empty()
        Vehicle.reset_counter()

    def call_planning(self):
        """Calls the (re)planning module and measures execution time.
        """
        log.info('Launch (re)planning...')
        start = time()
        self._decision_model(self.tcurrent)
        end = time()
        log.info(f'(Re)planning done in [{end - start:.5} s]')

    def call_update_graph(self, threshold):
        """Calls the graph update and measures execution time.
        """
        log.info(' Updating graph...')
        start = time()
        self._flow_motor.update_graph(threshold)
        end = time()
        log.info(f' Update graph done in [{end-start:.5} s]')

    def call_update_mobility_services(self, flow_dt:Dt):
        """Calls the update method of all mobility services and measures the execution
        times.

        Args:
            -flow_dt: the simulation flow time step
        """
        for layer in self._mlgraph.layers.values():
            for mservice in layer.mobility_services.values():
                log.info(f' Update mobility service {mservice.id}...')
                start = time()
                mservice.update(flow_dt)
                mservice.update_time(flow_dt)
                end = time()
                log.info(f' Update mobility service {mservice.id} done in [{end-start:.5} s]')

    def call_user_flow_step(self, flow_dt: Dt, users_step: List[User]):
        """Calls the user flow step and measures execution time.

        Args:
            -flow_dt: the simulation flow time step
            -users_step: list of users who departed during this flow step

        Returns:
            -users_reach_dt_answer: list of users who undergone a match failure
        """
        log.info(' Launch user flow step...')
        start = time()
        users_reach_dt_answer = self._user_flow.step(flow_dt, users_step)
        self._user_flow.update_time(flow_dt)
        end = time()
        log.info(f' User flow step done [{end - start:.5} s]')
        return users_reach_dt_answer

    def call_matching_mobility_services(self, new_users, flow_dt):
        """Calls the matching for all mobility services and measures execution times.

        Args:
            -new_users: users who depart during this affectation step but have not
                        yet been taken into account by the UserFlow object
            -flow_dt: the flow time step
        """
        for layer in self._mlgraph.layers.values():
            for ms in layer.mobility_services.values():
                log.info(f' Perform matching for mobility service {ms.id}...')
                start = time()
                ms.launch_matching(new_users, self._user_flow, self._decision_model, flow_dt)
                end = time()
                log.info(f' Matching for mobility service {ms.id} done in [{end - start:.5} s]')

    def call_flow_motor_step(self, flow_dt: Dt):
        """Calls the flow motor step and measures execution time.

        Args:
            -flow_dt: the fow time step
        """
        log.info(' Launch flow motor step...')
        start = time()
        self._flow_motor.step(flow_dt)
        self._flow_motor.update_time(flow_dt)
        end = time()
        log.info(f' Flow motor step done in [{end - start:.5} s]')

    def step_dynamic_space_sharing(self):
        """Calls the dynamic space sharing update and reroutes vehicles impacted by
        the modification of available links.
        """
        # Call the dynamic space sharing update to unban and ban links when relevant, and reroute
        # vehicles consequently
        self._mlgraph.dynamic_space_sharing.update(self.tcurrent, list(VehicleManager._vehicles.values()))

    def get_new_users(self, principal_dt):
        """Gathers/Creates the users who depart during the coming affectation step.

        Args:
            -principal_dt: duration of one affectation step

        Returns:
            -new_users: list of users who depart during the coming affectation step
        """
        log.info(f'Getting next departures {self.tcurrent}->{self.tcurrent.add_time(principal_dt)} ...')
        new_users = []
        if self._demand:
            new_users = self._demand.get_next_departures(self.tcurrent, self.tcurrent.add_time(principal_dt))
            self._demand.construct_user_parameters(new_users)
        log.info(f'Getting next departures done: {len(new_users)} new departures')

        return new_users

    def get_users_step(self, new_users: List[User], flow_dt: Dt):
        """Gathers the users who depart during the coming simulation flow step.

        Args:
            -new_users: list of users who depart during the coming affectation step
            -flow_dt: the simulation flow time step

        Returns:
            -users_step: list of users who depart during the coming simulation flow step
            -remaining_new_users: list of users who depart during the coming affectation step without
                        users who depart during the coming simulation flow step
        """
        if new_users == []:
            return [], []
        next_time = self.tcurrent.add_time(flow_dt)
        iter_new_users = iter(new_users)
        u = next(iter_new_users)
        users_step = list()
        remaining_new_users = new_users.copy()
        try:
            while self.tcurrent <= u.departure_time < next_time:
                users_step.append(u)
                remaining_new_users.remove(u)
                u = next(iter_new_users)
        except StopIteration:
            pass
        return users_step, remaining_new_users

    def run(self, tstart: Time, tend: Time, flow_dt: Dt, affectation_factor: int, update_graph_threshold: float = 0., seed: int=None):
        """Launch a full simulation.

        Args:
            -tstart: simulation start time
            -tend: simulation end time
            -flow_dt: the simulation flow time step
            -affectation_factor: the number of simulation flow time step representing one affectation time step
            -update_graph_threshold: threshold on the speed variation below which costs on the graph links are not updated
            -seed: seed of the simulation
        """
        log.info(f'Start run from {tstart} to {tend}')

        ### Initializations
        self.set_random_seed(seed)
        self.initialize(tstart)
        affectation_step = 0
        flow_step = 0
        principal_dt = flow_dt * affectation_factor
        self.tcurrent = tstart
        progress = ProgressBar(ceil((tend-tstart).to_seconds()/(flow_dt.to_seconds()*affectation_factor)))

        ### Main loop
        while self.tcurrent < tend:
            progress.update()
            progress.show()
            log.info(f'Current time: {self.tcurrent}, affectation step: {affectation_step}')

            ## Get all departures during the next principal_dt and add the ones
            ## with no forced path in the list of users about to plan their journey
            new_users = self.get_new_users(principal_dt)
            new_users_for_planning = []
            for u in new_users:
                if u.path is None:
                    new_users_for_planning.append(u)
                else:
                    self._decision_model.manage_forced_initial_path(u)
            self._decision_model.add_users_for_planning(new_users_for_planning, [Event.DEPARTURE]*len(new_users_for_planning))

            ## Set pickup_dt to infinite for all PT mobility services
            pt_mob_services_names = self._mlgraph.get_all_mobility_services_of_type(PublicTransportMobilityService)
            for user in new_users:
                for pt_ms in pt_mob_services_names:
                    user.set_pickup_dt(pt_ms, Dt(hours=24))

            ## Call affectation_factor simulation flow steps
            for _ in range(affectation_factor):

                # Call the planning module
                self.call_planning()

                # Gather users who depart during this flow step
                users_step, new_users = self.get_users_step(new_users, flow_dt)
                log.info(f'Users step:{users_step}')

                # Call update of all mobility services, update means maintenance
                self.call_update_mobility_services(flow_dt)

                # Call user flow step
                users_reach_dt_answer = self.call_user_flow_step(flow_dt, users_step)
                self._decision_model.add_users_for_planning(users_reach_dt_answer, [Event.MATCH_FAILURE]*len(users_reach_dt_answer))

                # Call dynamic space sharing step
                self.step_dynamic_space_sharing()

                # Call matching for all mobility services
                self.call_matching_mobility_services(new_users, flow_dt)

                # Call flow motor step
                self.call_flow_motor_step(flow_dt)
                if self._flow_motor._write:
                    self._flow_motor.write_result(affectation_step, flow_step, flow_dt)

                # Update current time and current flow step number
                self.tcurrent = self.tcurrent.add_time(flow_dt)
                flow_step += 1

            ## Call the update graph
            self.call_update_graph(update_graph_threshold)

            if self._write:
                log.info('Writing costs of each link in graph ...')
                start = time()
                t_str = self._flow_motor.time
                for link in self._mlgraph.graph.links.values():
                    for mservice, costs in link.costs.items():
                        self._csvhandler.writerow([str(affectation_step), t_str, link.id, mservice, costs])
                end = time()
                log.info(f'Done [{end - start:.5} s]')

            ## Update affectation step number
            log.info('-'*50)
            affectation_step += 1

        ### Finalize simulation
        if self._user_flow._write:
            self._user_flow.write_result()
        self.finalize()
        progress.update()
        progress.show()
        progress.end()

    def create_crash_report(self, affectation_step, flow_step) -> dict:
        data = dict(time=str(self.tcurrent),
                    affectation_step=affectation_step,
                    flow_step=flow_step,
                    error=traceback.format_exc())

        return data
