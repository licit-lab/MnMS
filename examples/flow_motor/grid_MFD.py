from mnms.graph.generation import create_grid_graph
from mnms.graph.algorithms.walk import walk_connect
from mnms.demand.generation import create_random_demand
from mnms.flow.MFD import Reservoir, MFDFlow
from mnms.mobility_service import PersonalCar
from mnms.log import rootlogger, LOGLEVEL


rootlogger.setLevel(LOGLEVEL.INFO)

DIST = 1000

mmgraph = create_grid_graph(10, 5, DIST)
mmgraph.add_zone('ZONE', [l.id for l in mmgraph.flow_graph.links.values()])

car = PersonalCar('car_layer', 10)
bus = PersonalCar('bus', 10)

for n in mmgraph.flow_graph.nodes.keys():
    car.add_node('CAR_'+n, n)
    bus.add_node('BUS_'+n, n)

for l in mmgraph.flow_graph.links.values():
    uid = l.upstream_node
    did = l.downstream_node
    car.add_link('CAR_'+uid+'_'+did, 'CAR_'+uid, 'CAR_'+did, {'length': DIST}, [l.id])
    bus.add_link('BUS_' + uid + '_' + did, 'BUS_' + uid, 'BUS_' + did, {'length': DIST}, [l.id])

mmgraph.add_mobility_service(car)
mmgraph.add_mobility_service(bus)
mmgraph.mobility_graph.check()

walk_connect(mmgraph, 1)

demand = create_random_demand(mmgraph, "07:00:00", "10:00:00", cost_path='length', min_cost=5000)


def res_fct(dict_accumulations):
    V_car = 11.5 * (1 - (dict_accumulations['car_layer'] + dict_accumulations['bus']) / 80000)
    V_car = max(V_car, 0.001)
    V_bus = V_car / 2
    dict_speeds = {'car_layer': V_car, 'bus': V_bus}
    return dict_speeds


reservoir = Reservoir.fromZone(mmgraph, 'ZONE', res_fct)

flow_motor = MFDFlow()
flow_motor.set_graph(mmgraph)
flow_motor.add_reservoir(reservoir)
flow_motor.set_initial_demand(demand)
flow_motor.set_time("07:00:00")

dt = 120
for _ in range(100):
    flow_motor.update_time(dt)
    flow_motor.step(dt)
    print(flow_motor.time)
    flow_motor.update_graph()


print(flow_motor.hist_accumulations)
