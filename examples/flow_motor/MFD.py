from mnms.graph import MultiModalGraph
from mnms.demand.generate import create_random_demand
from mnms.tools.time import Time
from mnms.flow.MFD import Reservoir, MFDFlow

import numpy as np

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
    V_bus = V_car / 2
    dict_speeds = {'car': V_car, 'bus': V_bus}
    return dict_speeds


res1 = Reservoir.fromSensor(mmgraph, 'SEN1', res_fct1)
res2 = Reservoir.fromSensor(mmgraph, 'SEN2', res_fct2)

demand = create_random_demand(mmgraph, repeat=1, cost_path='time', distrib_time=lambda s, e: s)

for t, p in demand:
    print(t, p, sep='\t')
DT = 30
flow_motor = MFDFlow()
flow_motor.set_graph(mmgraph)
flow_motor.add_reservoir(res1)
flow_motor.add_reservoir(res2)
flow_motor.set_inital_demand(demand)
print(flow_motor._demand)

flow_motor._tcurrent = Time.fromSeconds(0)
flow_motor._demand = [[Time.fromSeconds(700), [{'length': 1200, 'mode': 'car', 'reservoir': "SEN1"},
                                               {'length': 200, 'mode': 'bus', 'reservoir': "SEN1"},
                                               {'length': 2000, 'mode': 'bus', 'reservoir': "SEN2"}]],
                      [Time.fromSeconds(78), [{'length': 2000, 'mode': 'car', 'reservoir': "SEN1"}]]]

flow_motor.nb_user = 2
flow_motor.accumulation_number = np.ones(flow_motor.nb_user)

flow_motor.initialize()
flow_motor._tcurrent = Time("00:00:00").add_time(seconds=DT)
for _ in range(33):
    flow_motor.update_time(DT)
    flow_motor.step(DT)
    print(flow_motor.hist_speeds)