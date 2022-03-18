from mnms import LOGLEVEL
from mnms.graph.core import MultiModalGraph
from mnms.graph.shortest_path import compute_shortest_path
from mnms.log import set_mnms_logger_level
from mnms.mobility_service.car import PersonalCarMobilityService, CarMobilityGraphLayer
from mnms.demand.user import User
from mnms.tools.time import Time, Dt
from mnms.demand.manager import BaseDemandManager
from mnms.simulation import Supervisor
from mnms.travel_decision.model import BaseDecisionModel
from mnms.tools.observer import CSVUserObserver
from mnms.flow.MFD import MFDFlow, Reservoir
from mnms.tools.observer import CSVVehicleObserver
import os



set_mnms_logger_level(LOGLEVEL.INFO, ['mnms.simulation',
                                      'mnms.vehicles.veh_type',
                                      'mnms.flow.user_flow',
                                      'mnms.flow.MFD',
                                      'mnms.layer.public_transport',
                                      'mnms.travel_decision.model',
                                      'mnms.tools.observer'])



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


car_layer = CarMobilityGraphLayer()
car_layer.add_node('C0', '0')
car_layer.add_node('C1', '1')
car_layer.add_node('C2', '2')
car_layer.add_node('C3', '3')

car_layer.add_link('C0_C1', 'C0', 'C1', {'length':1000}, ['0_1'])
car_layer.add_link('C1_C2', 'C1', 'C2', {'length':1000}, ['1_2'])
car_layer.add_link('C2_C3', 'C2', 'C3', {'length':1000}, ['2_3'])

car_layer.attach_vehicle_observer(CSVVehicleObserver(dir_path + "/veh.csv"))
car_layer.add_mobility_service(PersonalCarMobilityService())

mmgraph.add_layer(car_layer)
mmgraph.add_zone('ZONE', ['0_1', '1_2', '2_3'])

users = [User('U0', '0', '3', Time("07:00:00")),
         User('U1', '0', '3', Time("07:10:00")),
         User('U2', '0', '3', Time("07:20:00")),
         User('U3', '0', '3', Time("07:21:00"))]

obs = CSVUserObserver(dir_path+'/user.csv')
for u in users:
    u.attach(obs)

demand = BaseDemandManager(users)

decision = BaseDecisionModel(mmgraph, cost='length')


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