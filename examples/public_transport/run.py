###############
### Imports ###
###############
## Casuals
import pathlib

## MnMS
from mnms.log import set_all_mnms_logger_level, LOGLEVEL
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

##################
### Parameters ###
##################
demand_file = pathlib.Path(__file__).parent.joinpath('demand.csv').resolve()
log_file = pathlib.Path(__file__).parent.joinpath('sim.log').resolve()
roads_xmin = [0, 0]
roads_xmax = [3000, 0]
roads_nb_nodes = 2
bus_default_speed = 10 # m/s
bus_frequency = Dt(minutes=5)
bus_tstart = '07:01:00'
bus_tend = '08:01:00'
odlayer_connection_dist = 301 # m
def mfdspeed(dacc):
    dacc['BUS'] = 5 # m/s
    return dacc
tstart = Time("07:00:00")
tend = Time("08:30:00")
dt_flow = Dt(minutes=1)
affectation_factor = 10

#########################
### Scenario creation ###
#########################

#### RoadDescriptor ####
roads = generate_line_road(roads_xmin, roads_xmax, roads_nb_nodes)
roads.register_stop('SO', '0_1', 0.1)
roads.register_stop('S1', '0_1', 0.4)
roads.register_stop('S2', '0_1', 0.6)
roads.register_stop('SD', '0_1', 0.9)

#### MlGraph ####
bus_service = PublicTransportMobilityService('BUS')
ptlayer = PublicTransportLayer(roads, 'BUS', Bus, bus_default_speed, services=[bus_service],
    observer=CSVVehicleObserver("vehs.csv"))

ptlayer.create_line('L0',
                    ['SO', 'S1', 'S2','SD'],
                    [['0_1'], ['0_1'],['0_1']],
                    TimeTable.create_table_freq(bus_tstart, bus_tend, bus_frequency))

odlayer = generate_matching_origin_destination_layer(roads)

mlgraph = MultiLayerGraph([ptlayer],
                          odlayer,
                          odlayer_connection_dist)

#### Demand ####
demand = CSVDemandManager(demand_file)
demand.add_user_observer(CSVUserObserver('users.csv'))

#### Decision model ####
decision_model = DummyDecisionModel(mlgraph, outfile="paths.csv")

#### Flow motor ####
flow_motor = MFDFlowMotor()
flow_motor.add_reservoir(Reservoir(roads.zones['RES'], ['BUS'], mfdspeed))

#### Supervisor ####
supervisor = Supervisor(mlgraph,
                        demand,
                        flow_motor,
                        decision_model,
                        logfile=log_file,
                        loglevel=LOGLEVEL.INFO)

######################
### Run simulation ###
######################

set_all_mnms_logger_level(LOGLEVEL.INFO)

supervisor.run(tstart,
               tend,
               dt_flow,
               affectation_factor)
