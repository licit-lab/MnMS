from mnms.graph.core import MultiModalGraph
from mnms.graph.shortest_path import compute_shortest_path
from mnms.mobility_service.base import BaseMobilityService
from mnms.demand.user import User
from mnms.tools.time import Time, Dt
from mnms.demand.manager import BaseDemandManager
from mnms.simulation import Supervisor
from mnms.travel_decision.model import SimpleDecisionModel
from mnms.tools.observer import CSVUserObserver
from mnms.flow.MFD import MFDFlow, Reservoir
import os

dir_path = os.path.dirname(os.path.realpath(__file__))


mmgraph = MultiModalGraph()
fgraph = mmgraph.flow_graph

fgraph.add_node('0', [0, 0])
fgraph.add_node('1', [1000, 0])
fgraph.add_node('2', [2000, 0])
fgraph.add_node('3', [3000, 0])

fgraph.add_link('0_1', '0', '1')
fgraph.add_link('1_2', '1', '2')
fgraph.add_link('2_3', '2', '3')


car = BaseMobilityService('CAR', 10)
car.add_node('C0', '0')
car.add_node('C1', '1')
car.add_node('C2', '2')
car.add_node('C3', '3')

car.add_link('C0_C1', 'C0', 'C1', {'length':1}, ['0_1'])
car.add_link('C1_C2', 'C1', 'C2', {'length':1}, ['1_2'])
car.add_link('C2_C3', 'C2', 'C3', {'length':1}, ['2_3'])
mmgraph.add_mobility_service(car)
mmgraph.add_zone('ZONE', ['0_1', '1_2', '2_3'])


users = [User('U0', '0', '3', Time("07:00:00")),
         User('U1', '0', '3', Time("07:10:00")),
         User('U2', '0', '3', Time("07:20:00"))]

obs = CSVUserObserver(dir_path+'/user.csv')
for u in users:
    u.attach(obs)

demand = BaseDemandManager(users)

decision = SimpleDecisionModel(mmgraph, cost='length')


def res_fct(dict_accumulations):
    V_car = 11.5 * (1 - (dict_accumulations['CAR']) / 500)
    V_car = max(V_car, 0.001)
    dict_speeds = {'CAR': V_car}
    return dict_speeds


reservoir = Reservoir.fromZone(mmgraph, 'ZONE', res_fct)

flow_motor = MFDFlow()
flow_motor.add_reservoir(reservoir)

supervisor = Supervisor(graph=mmgraph,
                        demand=demand,
                        decision_model=decision,
                        flow_motor=flow_motor)

supervisor.run(Time("07:00:00"), Time("07:30:00"), Dt(seconds=1), 10)