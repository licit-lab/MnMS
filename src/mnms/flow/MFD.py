from typing import List
from copy import deepcopy
from typing import Callable, Dict

import numpy as np

from mnms.flow.abstract import AbstractFlowMotor
from mnms.graph.path import reconstruct_path
from mnms.graph.core import MultiModalGraph
from mnms.graph.elements import ConnectionLink
from mnms.log import rootlogger


class Reservoir(object):
    # id to identify the sensor, is not used for now, could be a string
    # modes are the transportation modes available for the sensor
    # fct_MFD_speed is the function returning the mean speeds as a function of the accumulations
    def __init__(self, id: str, modes, fct_MFD_speed: Callable[[Dict[str, float]], Dict[str, float]]):
        self.id = id
        self.modes = modes
        self.compute_MFD_speed = fct_MFD_speed
        dict_accumulations = {}
        for mode in modes:
            dict_accumulations[mode] = 0
        self.dict_accumulations = dict_accumulations
        self.dict_speeds = {}
        self.update_speeds()


    def update_accumulations(self, dict_accumulations):
        for mode in dict_accumulations.keys():
            if mode in self.modes:
                self.dict_accumulations[mode] = dict_accumulations[mode]
        return

    def update_speeds(self):
        self.dict_speeds = self.compute_MFD_speed(self.dict_accumulations)
        return self.dict_speeds

    @classmethod
    def fromZone(cls, mmgraph:"MultiModalGraph", zid:str, fct_MFD_speed):
        modes = set()
        for lid in mmgraph.zones[zid].links:
            nodes = mmgraph.flow_graph._map_lid_nodes[lid]
            for mobility_node in mmgraph.mobility_graph.get_node_references(nodes[0])+ mmgraph.mobility_graph.get_node_references(nodes[1]):
                modes.add(mmgraph.mobility_graph.nodes[mobility_node].mobility_service)

        new_res = Reservoir(zid, modes, fct_MFD_speed)
        return new_res


class MFDFlow(AbstractFlowMotor):
    def __init__(self):
        super(MFDFlow, self).__init__()
        self.reservoirs: List[Reservoir] = list()
        self.nb_user = 0
        self.accumulation_weights = [1]

    def initialize(self):
        print('Initializing MFD FLow Motor')
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
        self.accumulation_weights = np.ones(self.nb_user)

        self.initialize()

    def step(self, dt:float, new_users):
        time = self._tcurrent.to_seconds()
        rootlogger.debug(f"Time: {time}")
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
            rootlogger.debug(f"USER {self.departure_times[i_user].to_seconds()}")
            if (not self.started_trips[i_user]) and (self.departure_times[i_user].to_seconds() <= time):
                rootlogger.debug(f'New user entering the Network: {i_user}')
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
                                                 'speeds':  {}}
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
                    new_speed += length*speed
                    total_len += length
            new_speed = new_speed/total_len
            mobility_graph.links[mobility_graph._map_lid_nodes[tid]].costs['speed'] = new_speed
            mobility_graph.links[mobility_graph._map_lid_nodes[tid]].costs['time'] = new_speed*total_len

