from typing import List
from copy import deepcopy

from mnms.flow.abstract import AbstractFlowMotor
from mnms.flow.MFD import construct_leg
from mnms.tools.time import Time, Dt
from mnms.flow.MFD import Reservoir
from mnms.demand.user import User

import numpy as np

class MFDFlowEvent(AbstractFlowMotor):
    def __init__(self, outfile:str=None):
        super(MFDFlowEvent, self).__init__(outfile=outfile)
        if outfile is not None:
            self._csvhandler.writerow(
                ['AFFECTATION_STEP', 'FLOW_STEP', 'TIME', 'RESERVOIR', 'MODE', 'SPEED', 'ACCUMULATION'])

        self.reservoirs: List[Reservoir] = list()
        self.users = dict()

        self.dict_accumulations = None
        self.dict_speeds = None
        self.current_leg = None
        self.remaining_length = None
        self.current_mode = None
        self.current_reservoir = None
        self.time_completion_legs = None
        self.started_trips = None
        self.completed_trips = None
        self.nb_user = 0
        self.departure_times = None
        self.id_event = 0


    def initialize(self):
        #self.accumulation_weights = np.ones(self.nb_user)
        #self.departure_times = [dem[0] for dem in self._demand]
        self.dict_accumulations = {}
        self.dict_speeds = {}
        for res in self.reservoirs:
            self.dict_accumulations[res.id] = res.dict_accumulations
            self.dict_speeds[res.id] = res.dict_speeds
        self.dict_accumulations[None] = {m: 0 for r in self.reservoirs for m in r.modes} | {None: 0}
        self.dict_speeds[None] = {m: 0 for r in self.reservoirs for m in r.modes} | {None: 0}
        '''self.hist_accumulations = []
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
        self.completed_trips = [False] * self.nb_user'''

        self.current_leg = dict()
        self.remaining_length = dict()
        self.current_mode = dict()
        self.current_reservoir = dict()
        self.time_completion_legs = dict()
        self.started_trips = dict()
        self.completed_trips = dict()
        self.nb_user = 0
        self.departure_times = dict()
        self.id_event = 0


    def add_reservoir(self, res: Reservoir):
        self.reservoirs.append(res)

    '''def set_initial_demand(self, demand:List[List]):
        self._demand = list()
        for t, path in demand:
            recon_path = construct_leg(self._graph, path)
            for section in recon_path:
                section['reservoir'] = section.pop('sensor')
            self._demand.append([t, recon_path])
        self.nb_user = len(self._demand)
        self.accumulation_weights = np.ones(self.nb_user)

        self.initialize()'''


    def step(self, dt: Dt): # compute events during time step
        time = self._tcurrent.to_seconds() - dt.to_seconds() #  time at the start of the step
        time_cur = time #  current time

        # Update data structure for new users
        for nu in new_users:
            path = construct_leg(self._graph, nu.path)
            self._demand[nu.id] = path
            self.remaining_length[nu.id] = path[0]['length']
            self.current_mode[nu.id] = path[0]['mode']
            self.current_reservoir[nu.id] = path[0]['reservoir']
            self.current_leg[nu.id] = 0
            self.time_completion_legs[nu.id] = [-1] * len(path)

            self.departure_times[nu.id] = nu.departure_time
            self.started_trips[nu.id] = False
            self.completed_trips[nu.id] = False
            self.users[nu.id] = nu

        self.nb_user += len(new_users)
        # Find first next event
        # Find next entry
        waiting_entry = [i_user for i_user in self.users.keys() if not self.started_trips[i_user]]
        if waiting_entry:
            list_next_dept_time = [self.departure_times[d].to_seconds() for d in waiting_entry]
            id_next_entry = np.argmin(list_next_dept_time)
            t_next_entry = list_next_dept_time[id_next_entry]
        else:
            t_next_entry = np.infty
        # Find next exit (from leg)
        running = [i_user for i_user in self.users.keys() if self.started_trips[i_user] and not self.completed_trips[i_user]]
        if running:
            list_next_exit = [self.remaining_length[i_user]/self.dict_speeds[
                self.current_reservoir[i_user]][self.current_mode[i_user]] for i_user in running]
            id_next_exit = np.argmin(list_next_exit)
            t_next_exit = time_cur + list_next_exit[id_next_exit]
        else:
            t_next_exit = np.infty
        entry_is_next = t_next_entry < t_next_exit
        t_new = min(t_next_entry, t_next_exit)
        #-- Begin loop on events
        while t_new <= time + dt.to_seconds():
            self.id_event += 1
            if entry_is_next:
                for i in running:
                    v = self.dict_speeds[
                self.current_reservoir[i]][self.current_mode[i]]
                    self.remaining_length[i] -= v * (t_new - time_cur)
                # add new user
                i_user = waiting_entry[id_next_entry]
                self.dict_accumulations[self.current_reservoir[i_user]][self.current_mode[i_user]] += \
                self.users[i_user].scale_factor
                self.started_trips[i_user] = True
                #self.exit_user_per_event.append(-1)
                #self.event_start_per_user[i_user] = self.id_event
            else: # user finishes trip leg
                for i in running:
                    v = self.dict_speeds[
                        self.current_reservoir[i]][self.current_mode[i]]
                    self.remaining_length[i] -= v * (t_new - time_cur)
                # user left current leg
                i_user = running[id_next_exit]
                curr_leg = self.current_leg[i_user]
                self.dict_accumulations[self.current_reservoir[i_user]][self.current_mode[i_user]] -= \
                    self.users[i_user].scale_factor
                self.time_completion_legs[i_user][curr_leg] = t_new
                #self.event_exit_per_user[i_user][curr_leg] = self.id_event
                if self.current_leg[i_user] < len(self._demand[i_user][1]) - 1: # still some legs to complete
                    self.current_leg[i_user] += 1
                    path = self._demand[i_user]
                    curr_leg = self.current_leg[i_user]
                    self.remaining_length[i_user] = path[curr_leg]['length']
                    self.current_mode[i_user] = path[curr_leg]['mode']
                    self.current_reservoir[i_user] = path[curr_leg]['reservoir']
                    curr_mode = self.current_mode[i_user]
                    curr_res = self.current_reservoir[i_user]
                    self.dict_accumulations[curr_res][curr_mode] += self.users[i_user].scale_factor
                else: # finish the trip
                    self.completed_trips[i_user] = True
                    user = self.users[i_user]
                    user.arrival_time = Time.fromSeconds(t_next_exit) #TODO to check

                    del self.users[i_user]
                    del self.completed_trips[i_user]
                    del self.started_trips[i_user]
                    del self.remaining_length[i_user]
                    del self.current_mode[i_user]
                    del self.current_leg[i_user]
                    del self.current_reservoir[i_user]
                    del self.time_completion_legs[i_user]
                    self.nb_user -= 1

                #self.exit_user_per_event.append(i_user)
            # See later if virtual length is needed
            '''virt_len_loc = {}
            for res in self.reservoirs:
                virt_len_loc[res.id] = {}
                for mode in res.modes:
                    v = self.list_dict_speeds[res.id][mode]
                    virt_len_loc[res.id][mode] = self.hist_virtual_lengths[-1][res.id][mode] + v*(t_new - time_cur)'''
            #self.hist_virtual_lengths.append(virt_len_loc.copy())

            # Update the traffic conditions
            for i_res, res in enumerate(self.reservoirs):
                res.update_accumulations(self.dict_accumulations[res.id])
                res.update_speeds()
                self.dict_speeds[res.id] = res.update_speeds()
            # See later if needed
            #self.hist_accumulations.append(deepcopy(self.list_dict_accumulations))
            #self.hist_speeds.append(self.list_dict_speeds.copy())

            # Compute time of next event to check if it's still in the time step
            # Find next entry - improvement idea: calculate it once and update the list
            time_cur = t_new
            waiting_entry = [i_user for i_user in self.users.keys() if not self.started_trips[i_user]]
            if waiting_entry:
                list_next_dept_time = [self.departure_times[d].to_seconds() for d in waiting_entry]
                id_next_entry = np.argmin(list_next_dept_time)
                t_next_entry = list_next_dept_time[id_next_entry]
            else:
                t_next_entry = np.infty
            # Find next exit (from leg) - improvement idea: calculate it once and update the list
            running = [i_user for i_user in self.users.keys() if self.started_trips[i_user] and not self.completed_trips[i_user]]
            if running:
                list_next_exit = [self.remaining_length[i_user] / self.dict_speeds[
                    self.current_reservoir[i_user]][self.current_mode[i_user]] for i_user in running]
                id_next_exit = np.argmin(list_next_exit)
                t_next_exit = time_cur + list_next_exit[id_next_exit]
            else:
                t_next_exit = np.infty
            entry_is_next = t_next_entry < t_next_exit
            t_new = min(t_next_entry, t_next_exit)
        #-- End loop on events
        # Move the agents until the end of the time step
        for i in running:
            v = self.dict_speeds[
                self.current_reservoir[i]][self.current_mode[i]]
            self.remaining_length[i] -= v * (time + dt.to_seconds() - time_cur)

    def update_graph(self):
        mobility_graph = self._graph.mobility_graph
        flow_graph = self._graph.flow_graph
        topolink_lenghts = dict()
        res_links = {res.id: self._graph.zones[res.id].links for res in self.reservoirs}
        res_dict = {res.id: res for res in self.reservoirs}

        for tid, topolink in mobility_graph.links.items():
            if isinstance(topolink, ConnectionLink):
                link_service = topolink.mobility_service
                topolink_lenghts[topolink.id] = {'lengths': {},
                                                 'speeds': {}}
                for l in topolink.reference_links:
                    topolink_lenghts[topolink.id]['lengths'][l] = flow_graph.links[flow_graph._map_lid_nodes[l]].length
                    topolink_lenghts[topolink.id]['speeds'][l] = None
                    for resid, reslinks in res_links.items():
                        res = res_dict[resid]
                        if l in reslinks:
                            mspeed = res.dict_speeds[link_service]
                            topolink_lenghts[topolink.id]['speeds'][l] = mspeed
                            break

        for tid, tdata in topolink_lenghts.items():
            total_len = 0
            new_speed = 0
            for gid, length in tdata['lengths'].items():
                speed = tdata['speeds'][gid]
                if speed is not None:
                    new_speed += length * speed
                    total_len += length
                else:
                    link_node = mobility_graph._map_lid_nodes[tid]
                    link = mobility_graph.links[link_node]
                    new_speed = self._graph._mobility_services[link.mobility_service].default_speed
            new_speed = new_speed / total_len if total_len != 0 else new_speed
            mobility_graph.links[mobility_graph._map_lid_nodes[tid]].costs['speed'] = new_speed
            mobility_graph.links[mobility_graph._map_lid_nodes[tid]].costs['time'] = total_len / new_speed

    def write_result(self, step_affectation: int, step_flow: int):
        tcurrent = self._tcurrent.time
        for res in self.reservoirs:
            resid = res.id
            for mode in res.modes:
                self._csvhandler.writerow(
                    [str(step_affectation), str(step_flow), tcurrent, resid, mode, res.dict_speeds[mode],
                     res.dict_accumulations[mode]])
