from typing import List
from copy import deepcopy

from mnms.flow.abstract import AbstractFlowMotor
from mnms.graph.path import reconstruct_path
from mnms.tools.time import Time
from mnms.flow.MFD import Reservoir

import numpy as np

class MFDFlowEvent(AbstractFlowMotor):
    def __init__(self):
        super(MFDFlowEvent, self).__init__()
        self.reservoirs = list()
        self.nb_user = 0
        self.accumulation_weights = [1]


    def initialize(self):
        self.accumulation_weights = np.ones(self.nb_user)
        self.departure_times = [dem[0] for dem in self._demand]
        self.list_dict_accumulations = {}
        self.list_dict_speeds = {}
        for res in self.reservoirs:
            self.list_dict_accumulations[res.id] = res.dict_accumulations
            self.list_dict_speeds[res.id] = res.dict_speeds
        self.hist_accumulations = []
        self.hist_speeds = []
        self.hist_virtual_lengths = []
        virt_len_loc = {}
        for res in self.reservoirs:
            virt_len_loc[res.id] = {}
            for mode in res.modes:
                virt_len_loc[res.id][mode] = 0
        self.hist_virtual_lengths.append(virt_len_loc.copy())

        self.list_current_leg = np.zeros(self.nb_user, dtype='int')
        self.list_remaining_length = np.zeros(self.nb_user)
        self.list_current_mode = [0] * self.nb_user
        self.list_current_reservoir = {i: None for i in range(self.nb_user)}
        self.list_time_completion_legs = []

        self.exit_user_per_event = [-1]
        self.event_start_per_user = np.zeros(self.nb_user, dtype='int')
        self.event_exit_per_user = []
        self.id_event = 0
        for i_user in range(self.nb_user):
            sections = self._demand[i_user][1]
            self.list_remaining_length[i_user] = sections[self.list_current_leg[i_user]]['length']
            self.list_current_mode[i_user] = sections[self.list_current_leg[i_user]]['mode']
            self.list_current_reservoir[i_user] = sections[self.list_current_leg[i_user]]['reservoir']
            self.list_time_completion_legs.append([-1] * len(self._demand[i_user][1]))
            self.event_exit_per_user.append([-1] * len(self._demand[i_user][1]))

        self.started_trips = [False] * self.nb_user
        self.completed_trips = [False] * self.nb_user



    def add_reservoir(self, res: Reservoir):
        self.reservoirs.append(res)

    def set_initial_demand(self, demand:List[List]):
        self._demand = list()
        for t, path in demand:
            recon_path = reconstruct_path(self._graph, path)
            for section in recon_path:
                section['reservoir'] = section.pop('sensor')
            self._demand.append([t, recon_path])
        self.nb_user = len(self._demand)
        self.accumulation_weights = np.ones(self.nb_user)

        self.initialize()


    def step(self): # time step is internal, depends on the next event
        time = self._tcurrent.to_seconds()
        self.id_event += 1

        # Find next entry
        waiting_entry = [d for d in range(self.nb_user) if not self.started_trips[d]]
        if waiting_entry:
            list_next_dept_time = [self.departure_times[d].to_seconds() for d in waiting_entry]
            id_next_entry = np.argmin(list_next_dept_time)
            t_next_entry = list_next_dept_time[id_next_entry]
        else:
            t_next_entry = np.infty
        # Find next exit (from leg)
        running = [d for d in range(self.nb_user) if self.started_trips[d] and not self.completed_trips[d]]
        if running:
            list_next_exit = [self.list_remaining_length[i_user]/self.list_dict_speeds[
                self.list_current_reservoir[i_user]][self.list_current_mode[i_user]] for i_user in running]
            id_next_exit = np.argmin(list_next_exit)
            t_next_exit = time + list_next_exit[id_next_exit]
        else:
            t_next_exit = np.infty
        entry_is_next = t_next_entry < t_next_exit
        if entry_is_next:
            t_new = t_next_entry
            for i in running:
                v = self.list_dict_speeds[
            self.list_current_reservoir[i]][self.list_current_mode[i]]
                self.list_remaining_length[i] -= v * (t_new - time)
            # add new user
            i_user = waiting_entry[id_next_entry]
            self.list_dict_accumulations[self.list_current_reservoir[i_user]][self.list_current_mode[i_user]] += \
            self.accumulation_weights[i_user]
            self.started_trips[i_user] = True
            self.exit_user_per_event.append(-1)
            self.event_start_per_user[i_user] = self.id_event
        else: # user finishes trip leg
            t_new = t_next_exit
            for i in running:
                v = self.list_dict_speeds[
                    self.list_current_reservoir[i]][self.list_current_mode[i]]
                self.list_remaining_length[i] -= v * (t_new - time)
            # user left current leg
            i_user = running[id_next_exit]
            curr_leg = self.list_current_leg[i_user]
            self.list_dict_accumulations[self.list_current_reservoir[i_user]][self.list_current_mode[i_user]] -= \
                self.accumulation_weights[i_user]
            self.list_time_completion_legs[i_user][curr_leg] = t_new
            self.event_exit_per_user[i_user][curr_leg] = self.id_event
            if self.list_current_leg[i_user] < len(self._demand[i_user][1]) - 1: # still some legs to complete
                self.list_current_leg[i_user] += 1
                path = self._demand[i_user][1]
                curr_leg = self.list_current_leg[i_user]
                self.list_remaining_length[i_user] = path[curr_leg]['length']
                self.list_current_mode[i_user] = path[curr_leg]['mode']
                self.list_current_reservoir[i_user] = path[curr_leg]['reservoir']
                curr_mode = self.list_current_mode[i_user]
                curr_res = self.list_current_reservoir[i_user]
                self.list_dict_accumulations[curr_res][curr_mode] += self.accumulation_weights[i_user]
            else: # finish the trip
                self.completed_trips[i_user] = True
            self.exit_user_per_event.append(i_user)
        self._tcurrent = Time.fromSeconds(t_new)
        virt_len_loc = {}
        for res in self.reservoirs:
            virt_len_loc[res.id] = {}
            for mode in res.modes:
                v = self.list_dict_speeds[res.id][mode]
                virt_len_loc[res.id][mode] = self.hist_virtual_lengths[-1][res.id][mode] + v*(t_new - time)
        self.hist_virtual_lengths.append(virt_len_loc.copy())

        # Update the traffic conditions
        for i_res, res in enumerate(self.reservoirs):
            res.update_accumulations(self.list_dict_accumulations[res.id])
            res.update_speeds()
            self.list_dict_speeds[res.id] = res.update_speeds()
        self.hist_accumulations.append(deepcopy(self.list_dict_accumulations))
        self.hist_speeds.append(self.list_dict_speeds.copy())

    def update_graph(self, mmgraph):
        pass