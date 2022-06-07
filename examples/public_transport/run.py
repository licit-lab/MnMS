import pathlib

from mnms import LOGLEVEL
from mnms.demand import CSVDemandManager
from mnms.flow.MFD import Reservoir, MFDFlow
from mnms.generation.roads import generate_line_road
from mnms.generation.layers import generate_matching_origin_destination_layer
from mnms.graph.layers import PublicTransportLayer, MultiLayerGraph
from mnms.log import set_mnms_logger_level
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.simulation import Supervisor
from mnms.tools.observer import CSVUserObserver
from mnms.travel_decision import DummyDecisionModel
from mnms.vehicles.veh_type import Bus
from mnms.time import TimeTable, Time, Dt


set_mnms_logger_level(LOGLEVEL.INFO, ['mnms.simulation',
                                      'mnms.vehicles.veh_type',
                                      'mnms.flow.user_flow',
                                      'mnms.flow.MFD',
                                      'mnms.layer.public_transport',
                                      'mnms.travel_decision.dummy',
                                      'mnms.tools.observer'])

cwd = pathlib.Path(__file__).parent.joinpath('demand.csv').resolve()

# Graph

roaddb = generate_line_road([0, 0], [0, 3000], 4)
roaddb.register_stop('S0', '0_1', 0.10)
roaddb.register_stop('S1', '1_2', 0.50)
roaddb.register_stop('S2', '2_3', 0.99)

bus_service = PublicTransportMobilityService('B0')
pblayer = PublicTransportLayer('BUS',
                               roaddb,
                               Bus,
                               13,
                               services=[bus_service])

pblayer.create_line('L0',
                    ['S0', 'S1', 'S2'],
                    [['0_1', '1_2'], ['1_2', '2_3']],
                    TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=5)))

odlayer = generate_matching_origin_destination_layer(roaddb)

# road_db = generate_manhattan_road(10, 100)
# car_layer = generate_layer_from_roads(road_db,
#                                       'CAR',
#                                       mobility_services=[PersonalCarMobilityService()])
#
# odlayer = generate_grid_origin_destination_layer(0, 0, 1000, 1000, 10, 10)

mlgraph = MultiLayerGraph([pblayer],
                          odlayer,
                          200)

# Demand

demand = CSVDemandManager(cwd, demand_type='coordinate')
demand.add_user_observer(CSVUserObserver('user.csv'))

# Decison Model

decision_model = DummyDecisionModel(mlgraph)

# Flow Motor

def mfdspeed(dacc):
    dacc['CAR'] = 3
    return dacc

flow_motor = MFDFlow()
flow_motor.add_reservoir(Reservoir('RES', 'BUS', mfdspeed))

supervisor = Supervisor(mlgraph,
                        demand,
                        flow_motor,
                        decision_model)

supervisor.run(Time("07:00:00"),
               Time("08:00:00"),
               Dt(seconds=10),
               10)