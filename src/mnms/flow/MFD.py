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

    def set_inital_demand(self, demand:List[List]):
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
        print('-'*50)
        time = self._tcurrent.to_seconds()
        print(self._tcurrent)
        # Update the traffic conditions
        for i_res, res in enumerate(self.reservoirs):
            res.update_accumulations(self.list_dict_accumulations[res.id])
            self.list_dict_speeds[res.id] = res.update_speeds()
        self.hist_accumulations.append(deepcopy(self.list_dict_accumulations))
        self.hist_speeds.append(self.list_dict_speeds.copy())

        # Move the agents
        for i_user in range(self.nb_user):
            # Agent enters the network
            if (not self.started_trips[i_user]) and (self.departure_times[i_user].to_seconds() <= time):
                self.started_trips[i_user] = True
                self.list_dict_accumulations[self.list_current_reservoir[i_user]][self.list_current_mode[i_user]] += self.accumulation_weights[i_user]

            # Agent is on the network
            if (not self.completed_trips[i_user]) and (self.started_trips[i_user]):
                remaining_time = time + dt
                # Complete current trip leg
                remaining_length = self.list_remaining_length[i_user]
                curr_res = self.list_current_reservoir[i_user]
                curr_mode = self.list_current_mode[i_user]
                curr_leg = self.list_current_leg[i_user]
                while remaining_length <= remaining_time * self.list_dict_speeds[curr_res][curr_mode] and curr_leg < len(self._demand[i_user][1]) - 1:
                    remaining_time -= self.list_remaining_length[i_user] / self.list_dict_speeds[self.list_current_reservoir[i_user]][self.list_current_mode[i_user]]
                    self.list_dict_accumulations[self.list_current_reservoir[i_user]][self.list_current_mode[i_user]] -= self.accumulation_weights[i_user]

                    self.list_time_completion_legs[i_user][self.list_current_leg[i_user]] = time
                    self.list_current_leg[i_user] += 1

                    path = self._demand[i_user][1]
                    curr_leg  = self.list_current_leg[i_user]
                    curr_mode = self.list_current_mode[i_user]
                    curr_res = self.list_current_reservoir[i_user]
                    self.list_remaining_length[i_user] = path[curr_leg]['length']
                    self.list_current_mode[i_user] = path[curr_leg]['mode']
                    self.list_current_reservoir[i_user] = path[curr_leg]['reservoir']
                    self.list_dict_accumulations[curr_res][curr_mode] += self.accumulation_weights[i_user]
                # Remove accomplished distance
                self.list_remaining_length[i_user] -= remaining_time * self.list_dict_speeds[self.list_current_reservoir[i_user]][
                    self.list_current_mode[i_user]]
                # Remove agent who reached destinations
                if self.list_remaining_length[i_user] <= 0:
                    # Improvement pt: could take the ratio of remaining distance over possible distance to be more accurate
                    self.list_dict_accumulations[self.list_current_reservoir[i_user]][self.list_current_mode[i_user]] -= \
                        self.accumulation_weights[i_user]
                    curr_leg = self.list_current_leg[i_user]
                    self.list_time_completion_legs[i_user][curr_leg] = time
                    self.completed_trips[i_user] = True
        # print(self.completed_trips)
        return self.list_time_completion_legs, self.hist_accumulations, self.hist_speeds



if __name__ == "__main__":
    from mnms.graph import MultiModalGraph
    from mnms.demand.generate import create_random_demand

    mmgraph = MultiModalGraph()
    flow = mmgraph.flow_graph
    mobility = mmgraph.mobility_graph

    flow.add_node('0', [0, 0])
    flow.add_node('1', [1, 0])
    flow.add_node('2', [2, 0])
    flow.add_node('3', [3, 0])

    flow.add_link('0_1', '0', '1', length=1000)
    flow.add_link('1_0', '1', '0', length=1000)

    flow.add_link('1_2', '1', '2', length=200)
    flow.add_link('2_1', '2', '1', length=200)

    flow.add_link('2_3', '2', '3', length=3000)
    flow.add_link('3_2', '3', '2', length=3000)

    mmgraph.add_sensor('SEN1', ['0_1', '1_0', '1_2', '2_1'])
    mmgraph.add_sensor('SEN2', ['2_3', '3_2'])

    m1 = mmgraph.add_mobility_service('car')
    m1.add_node('0', '0')
    m1.add_node('1', '1')
    m1.add_node('3', '3')
    m1.add_link('M1_0_1', '0', '1', {'time': 1}, ['0_1'])
    m1.add_link('M1_1_0', '1', '0', {'time': 1}, ['1_0'])

    m1.add_link('M1_1_3', '1', '3', {'time': 1}, ['1_2', '2_3'])
    m1.add_link('M1_3_1', '3', '1', {'time': 1}, ['3_2', '2_1'])

    m2 = mmgraph.add_mobility_service('bus')
    m2.add_node('0', '0')
    m2.add_node('1', '1')
    m2.add_node('3', '3')
    m2.add_link('M2_0_1', '0', '1', {'time': 10}, ['0_1'])
    m2.add_link('M2_1_0', '1', '0', {'time': 10}, ['1_0'])
    m2.add_link('M2_1_3', '1', '3', {'time': 20}, ['1_2', '2_3'])
    m2.add_link('M2_3_1', '3', '1', {'time': 20}, ['3_2', '2_1'])

    mmgraph.connect_mobility_service('M1', 'M2', '1', {"time": 0})

    def res_fct1(dict_accumulations):
        V_car = 0
        if dict_accumulations['car'] < 18000:
            V_car = 11.5 - dict_accumulations['car'] * 6 / 18000
        elif dict_accumulations['car'] < 55000:
            V_car = 11.5 - 6 - (dict_accumulations['car'] - 18000) * 4.5 / (55000 - 18000)
        elif dict_accumulations['car'] < 80000:
            V_car = 11.5 - 6 - 4.5 - (dict_accumulations['car'] - 55000) * 1 / (80000 - 55000)
        V_car = max(V_car, 0.001)
        V_bus = 4
        dict_speeds = {'car': V_car, 'bus': V_bus}
        return dict_speeds


    def res_fct2(dict_accumulations):
        V_car = 11.5 * (1 - (dict_accumulations['car'] + dict_accumulations['bus']) / 80000)
        V_car = max(V_car, 0.001)
        V_bus = V_car/2
        dict_speeds = {'car': V_car, 'bus': V_bus}
        return dict_speeds

    res1 = Reservoir.fromSensor(mmgraph, 'SEN1', res_fct1)
    res2 = Reservoir.fromSensor(mmgraph, 'SEN2', res_fct2)


    demand = create_random_demand(mmgraph, repeat=1, cost_path='time', distrib_time=lambda s, e: s)
    for t, p in demand:
        print(t, p ,sep='\t')
    DT = 30
    flow_motor = MFDFlow()
    flow_motor.set_graph(mmgraph)
    flow_motor.add_reservoir(res1)
    flow_motor.add_reservoir(res2)
    flow_motor.set_inital_demand(demand)
    print(flow_motor._demand)
    flow_motor._tcurrent = Time.fromSeconds(0)
    flow_motor._demand = [[Time.fromSeconds(700), [{'length': 1200, 'mode': 'car', 'reservoir': "SEN1"}, {'length': 200, 'mode': 'bus', 'reservoir': "SEN1"},
                  {'length': 2000, 'mode': 'bus', 'reservoir': "SEN2"}]],
                 [Time.fromSeconds(78), [{'length': 2000, 'mode': 'car', 'reservoir': "SEN1"}]]]

    flow_motor.nb_user = 2
    flow_motor.accumulation_number = np.ones(flow_motor.nb_user)

    flow_motor.initialize()
    flow_motor._tcurrent = Time("00:00:00").add_time(seconds=DT)
    for _ in range(33):
        flow_motor._tcurrent = flow_motor._tcurrent.add_time(seconds=DT)
        print(flow_motor.step(DT)[2])
