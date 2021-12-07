from typing import List
from copy import deepcopy

from mnms.flow.abstract import AbstractFlowMotor
from mnms.graph.path import reconstruct_path
from mnms.tools.time import Time

import numpy as np

class Reservoir(object):
    # id to identify the sensor, is not used for now, could be a string
    # modes are the transportation modes available for the sensor
    # fct_MFD_speed is the function returning the mean speeds as a function of the accumulations
    def __init__(self, id: str, modes, fct_MFD_speed):
        self.id = id
        self.modes = modes
        self.compute_MFD_speed = fct_MFD_speed
        dict_accumulations = {}
        for mode in modes:
            dict_accumulations[mode] = 0
        self.dict_accumulations = dict_accumulations
        self.dict_speeds = {}
        self.update_speeds()
        return

    def update_accumulations(self, dict_accumulations):
        for mode in dict_accumulations.keys():
            if mode in self.modes:
                self.dict_accumulations[mode] = dict_accumulations[mode]
        return

    def update_speeds(self):
        self.dict_speeds = self.compute_MFD_speed(self.dict_accumulations)
        return self.dict_speeds

    @classmethod
    def fromSensor(cls, mmgraph:"MultiModalGraph", sid:str, fct_MFD_speed):
        modes = set()
        for lid in mmgraph.sensors[sid].links:
            nodes = mmgraph.flow_graph._map_lid_nodes[lid]
            for mobility_node in mmgraph.node_referencing[nodes[0]] + mmgraph.node_referencing[nodes[1]]:
                modes.add(mmgraph.mobility_graph.nodes[mobility_node].mobility_service)

        new_res = Reservoir(sid, modes, fct_MFD_speed)
        return new_res

class MFDFlow(AbstractFlowMotor):
    def __init__(self):
        super(MFDFlow, self).__init__()
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

        self.list_current_leg = np.zeros(self.nb_user, dtype='int')
        self.list_remaining_length = np.zeros(self.nb_user)
        self.list_current_mode = [0] * self.nb_user
        self.list_current_reservoir = {i: None for i in range(self.nb_user)}
        self.list_time_completion_legs = []

        for i_user in range(self.nb_user):
            sections = self._demand[i_user][1]
            self.list_remaining_length[i_user] = sections[self.list_current_leg[i_user]]['length']
            self.list_current_mode[i_user] = sections[self.list_current_leg[i_user]]['mode']
            self.list_current_reservoir[i_user] = sections[self.list_current_leg[i_user]]['reservoir']
            self.list_time_completion_legs.append([-1] * len(self._demand[i_user][1]))
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
        self.accumulation_number = np.ones(self.nb_user)

        self.initialize()


    def step(self, dt:float):
        time = self._tcurrent.to_seconds()
        # Update the traffic conditions
        for i_res, res in enumerate(self.reservoirs):
            res.update_accumulations(self.list_dict_accumulations[res.id])
            self.list_dict_speeds[res.id] = res.update_speeds()
        self.hist_accumulations.append(deepcopy(self.list_dict_accumulations))
        self.hist_speeds.append(self.list_dict_speeds.copy())

        # Move the agents
        for i_user in range(self.nb_user):
            remaining_time = dt
            # Agent enters the network
            if (not self.started_trips[i_user]) and (self.departure_times[i_user].to_seconds() <= time):
                self.started_trips[i_user] = True
                self.list_dict_accumulations[self.list_current_reservoir[i_user]][self.list_current_mode[i_user]] += self.accumulation_weights[i_user]
                remaining_time = time - self.departure_times[i_user].to_seconds()

            # Agent is on the network
            if (not self.completed_trips[i_user]) and (self.started_trips[i_user]):
                # Complete current trip leg
                remaining_length = self.list_remaining_length[i_user]
                curr_res = self.list_current_reservoir[i_user]
                curr_mode = self.list_current_mode[i_user]
                curr_leg = self.list_current_leg[i_user]
                while remaining_length <= remaining_time * self.list_dict_speeds[curr_res][curr_mode] and curr_leg < len(self._demand[i_user][1]) - 1:
                    remaining_time -= remaining_length / self.list_dict_speeds[curr_res][curr_mode]
                    self.list_dict_accumulations[curr_res][curr_mode] -= self.accumulation_weights[i_user]
                    self.list_time_completion_legs[i_user][curr_leg] = time-remaining_time
                    self.list_current_leg[i_user] += 1

                    path = self._demand[i_user][1]
                    curr_leg  = self.list_current_leg[i_user]
                    self.list_remaining_length[i_user] = path[curr_leg]['length']
                    self.list_current_mode[i_user] = path[curr_leg]['mode']
                    self.list_current_reservoir[i_user] = path[curr_leg]['reservoir']
                    curr_mode = self.list_current_mode[i_user]
                    curr_res = self.list_current_reservoir[i_user]
                    self.list_dict_accumulations[curr_res][curr_mode] += self.accumulation_weights[i_user]
                # Remove agent who reached destinations
                if self.list_remaining_length[i_user] < remaining_time * self.list_dict_speeds[curr_res][curr_mode]:
                    self.list_dict_accumulations[curr_res][curr_mode] -= self.accumulation_weights[i_user]
                    remaining_time -= self.list_remaining_length[i_user] / self.list_dict_speeds[curr_res][curr_mode]
                    self.list_time_completion_legs[i_user][curr_leg] = time - remaining_time
                    self.completed_trips[i_user] = True
                    self.list_remaining_length[i_user]=0
                else:
                    # Remove accomplished distance when staying in on the network
                    self.list_remaining_length[i_user] -= remaining_time * self.list_dict_speeds[curr_res][curr_mode]

