from mnms.simulation import Supervisor
from mnms.graph.generation import create_grid_graph
from mnms.graph.algorithms.walk import walk_connect
from mnms.demand.generation import create_random_demand
from mnms.flow.MFD import Reservoir, MFDFlow
from mnms.mobility_service import BaseMobilityService
from mnms.log import rootlogger, LOGLEVEL
from mnms.tools.time import Time, Dt
from mnms.travel_decision.model import SimpleDecisionModel
from mnms.travel_decision.logit import LogitDecisionModel


rootlogger.setLevel(LOGLEVEL.INFO)

DIST = 1000


def create_simple_grid_multimodal():
    mmgraph = create_grid_graph(10, 5, DIST)
    mmgraph.add_zone('ZONE', [l.id for l in mmgraph.flow_graph.links.values()])

    car = BaseMobilityService('car', 10)
    bus = BaseMobilityService('bus', 10)

    for n in mmgraph.flow_graph.nodes.keys():
        car.add_node('CAR_'+n, n)
        bus.add_node('BUS_'+n, n)

    for l in mmgraph.flow_graph.links.values():
        uid = l.upstream_node
        did = l.downstream_node
        car.add_link('CAR_'+uid+'_'+did, 'CAR_'+uid, 'CAR_'+did, {'length': DIST, 'time':DIST/car.default_speed}, [l.id])
        bus.add_link('BUS_' + uid + '_' + did, 'BUS_' + uid, 'BUS_' + did, {'length': DIST, 'time':DIST/bus.default_speed}, [l.id])

    mmgraph.add_mobility_service(car)
    mmgraph.add_mobility_service(bus)
    mmgraph.mobility_graph.check()

    walk_connect(mmgraph, 1)

    return mmgraph


if __name__ == '__main__':
    mmgraph = create_simple_grid_multimodal()
    demand = create_random_demand(mmgraph, "07:00:00", "10:00:00", cost_path='length', min_cost=5000, seed=42)

    def res_fct(dict_accumulations):
        V_car = 11.5 * (1 - (dict_accumulations['car'] + dict_accumulations['bus']) / 80000)
        V_car = max(V_car, 0.001)
        V_bus = V_car / 2
        dict_speeds = {'car': V_car, 'bus': V_bus}
        return dict_speeds


    reservoir = Reservoir.fromZone(mmgraph, 'ZONE', res_fct)

    flow_motor = MFDFlow()
    flow_motor.add_reservoir(reservoir)

    travel_decision = LogitDecisionModel(mmgraph)

    supervisor = Supervisor()
    supervisor.add_graph(mmgraph)
    supervisor.add_flow_motor(flow_motor)
    supervisor.add_demand(demand)
    supervisor.add_decision_model(travel_decision)

    supervisor.update_graph_cost(3)

    supervisor.run(Time('07:00:00'), Time('10:00:00'), Dt(minutes=1), 10)
    pass