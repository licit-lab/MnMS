import pathlib

from mnms import LOGLEVEL
from mnms.demand import CSVDemandManager
from mnms.flow.MFD import Reservoir, MFDFlowMotor
from mnms.generation.layers import generate_matching_origin_destination_layer, generate_layer_from_roads, \
    generate_grid_origin_destination_layer
from mnms.generation.roads import generate_line_road, generate_manhattan_road
from mnms.graph.layers import PublicTransportLayer, MultiLayerGraph
from mnms.io.graph import save_graph, load_graph
from mnms.log import set_mnms_logger_level, attach_log_file
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.simulation import Supervisor
from mnms.time import TimeTable, Time, Dt
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.travel_decision import DummyDecisionModel
from mnms.vehicles.veh_type import Bus

set_mnms_logger_level(LOGLEVEL.INFO, ['mnms.simulation',
                                      'mnms.vehicles.veh_type',
                                      # 'mnms.flow.user_flow',
                                      'mnms.flow.MFD',
                                      'mnms.layer.public_transport',
                                      'mnms.mobility_service.public_transport',
                                      # 'mnms.travel_decision.dummy',
                                      'mnms.tools.observer'
                                      ])
attach_log_file('simulation.log')

cwd = pathlib.Path(__file__).parent.joinpath('demand.csv').resolve()

# Graph

roads = generate_line_road([0, 0], [0, 3000], 2)
roads.register_stop('SO', '0_1', 0.1)
roads.register_stop('S1', '0_1', 0.4)
roads.register_stop('S2', '0_1', 0.6)
roads.register_stop('SD', '0_1', 0.9)

bus_service = PublicTransportMobilityService('B0')

veh = pathlib.Path(__file__).parent.joinpath('veh.csv').resolve()
pblayer = PublicTransportLayer(roads, 'BUS', Bus, 10, services=[bus_service], observer=CSVVehicleObserver(veh))

pblayer.create_line('L0',
                    ['SO', 'S1', 'S2','SD'],
                    [['0_1'], ['0_1'],['0_1']],
                    TimeTable.create_table_freq('07:01:00', '08:01:00', Dt(minutes=5)))

odlayer = generate_matching_origin_destination_layer(roads)

#road_db = generate_manhattan_road(10, 100)

mlgraph = MultiLayerGraph([pblayer],
                          odlayer,
                          200)

# Demand
demand = CSVDemandManager(cwd)
demand.add_user_observer(CSVUserObserver('user.csv'))

# Decison Model

decision_model = DummyDecisionModel(mlgraph, outfile="path.csv")

# Flow Motor

def mfdspeed(dacc):
    dacc['BUS'] = 5
    return dacc

flow_motor = MFDFlowMotor()
flow_motor.add_reservoir(Reservoir(roads.zones['RES'], ['BUS'], mfdspeed))

supervisor = Supervisor(mlgraph,
                        demand,
                        flow_motor,
                        decision_model)

supervisor.run(Time("07:00:00"),
               Time("08:30:00"),
               Dt(minutes=1),
               10)
