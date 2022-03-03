from mnms.graph.core import MultiModalGraph
from mnms.mobility_service.public_transport import BusMobilityService
from mnms.mobility_service.personal_car import PersonalCar
from mnms.demand.user import User
from mnms.tools.time import Time, Dt, TimeTable
from mnms.demand.manager import BaseDemandManager
from mnms.simulation import Supervisor
from mnms.travel_decision.model import BaseDecisionModel
from mnms.tools.observer import CSVUserObserver
from mnms.flow.MFD import MFDFlow, Reservoir
from mnms.tools.observer import CSVVehicleObserver, CSVUserObserver
import os
from mnms.log import set_mnms_logger_level, LOGLEVEL


set_mnms_logger_level(LOGLEVEL.INFO, ['mnms.simulation',
                                      'mnms.vehicles.veh_type',
                                      'mnms.flow.user_flow',
                                      'mnms.flow.MFD',
                                      'mnms.mobility_service.public_transport',
                                      'mnms.travel_decision.model',
                                      'mnms.tools.observer'])

# set_mnms_logger_level(LOGLEVEL.INFO, ['mnms.graph.shortest_path'])

dir_path = os.path.dirname(os.path.realpath(__file__))


mmgraph = MultiModalGraph()
fgraph = mmgraph.flow_graph

fgraph.add_node('0', [0, 0])
fgraph.add_node('1', [1000, 0])
fgraph.add_node('2', [2000, 0])
fgraph.add_node('3', [3000, 0])
fgraph.add_node('4', [2000, 1000])

fgraph.add_link('0_1', '0', '1')
fgraph.add_link('1_2', '1', '2')
fgraph.add_link('2_3', '2', '3')
fgraph.add_link('2_4', '2', '4')


bus = BusMobilityService('Bus', 10)
line = bus.add_line('L1', TimeTable.create_table_freq('07:00:00', '20:00:00', Dt(seconds=2)))
# print(line.timetable.table)
# print(line.new_departures(Time("07:00:01"), Dt(seconds=2)))

line.add_stop('C0', '0')
line.add_stop('C1', '1')
line.add_stop('C2', '2')
line.add_stop('C4', '4')

line.connect_stops('C0_C1', 'C0', 'C1', 1000, reference_links=['0_1'])
line.connect_stops('C1_C2', 'C1', 'C2', 1000, reference_links=['1_2'])
line.connect_stops('C2_C4', 'C2', 'C4', 1000, reference_links=['2_4'])

bus.attach_vehicle_observer(CSVVehicleObserver(dir_path+"/veh.csv"))

car = PersonalCar('Car', 10)

car.add_node('A2', '2')
car.add_node('A3', '3')

car.add_link('A2_A3', 'A2', 'A3', {'length': 1000}, reference_links=['2_3'])

mmgraph.add_mobility_service(car)
mmgraph.add_mobility_service(bus)
mmgraph.connect_mobility_service('C2_A2', 'L1_C2', 'A2', 10, {'time':10})
mmgraph.add_zone('ZONE', ['0_1', '1_2', '2_3', '2_4'])


# users = [User('U0', '0', '3', Time("07:00:00"), available_mobility_services=['Bus', 'WALK']),
#          User('U1', '0', '3', Time("07:10:00"), available_mobility_services=['Bus', 'WALK']),
#          User('U2', '0', '3', Time("07:20:00"), available_mobility_services=['Bus', 'WALK']),
#          User('U3', '0', '3', Time("07:21:00"), available_mobility_services=['Bus', 'WALK'])]


users = [User('U0', '0', '3', Time("07:01:00"), available_mobility_services=['Bus', 'Car',  'WALK'])]

obs = CSVUserObserver(dir_path+'/user.csv')
for u in users:
    u.attach(obs)

demand = BaseDemandManager(users)

decision = BaseDecisionModel(mmgraph, cost='length')


def res_fct(dict_accumulations):
    V_car = 11.5 * (1 - (dict_accumulations['BUS']) / 500)
    V_car = max(V_car, 0.001)
    dict_speeds = {'BUS': V_car, 'CAR': V_car}
    return dict_speeds


reservoir = Reservoir.fromZone(mmgraph, 'ZONE', res_fct)

flow_motor = MFDFlow()
flow_motor.add_reservoir(reservoir)

supervisor = Supervisor(graph=mmgraph,
                        demand=demand,
                        decision_model=decision,
                        flow_motor=flow_motor)

supervisor.run(Time("07:00:00"), Time("07:08:50"), Dt(seconds=2), 10)
