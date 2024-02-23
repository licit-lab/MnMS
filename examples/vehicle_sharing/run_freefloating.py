###############
### Imports ###
###############
## Casuals
import pathlib

# MnMS
from mnms.generation.roads import generate_manhattan_road
from mnms.mobility_service.vehicle_sharing import VehicleSharingMobilityService
from mnms.tools.observer import CSVVehicleObserver, CSVUserObserver
from mnms.generation.layers import generate_layer_from_roads, generate_grid_origin_destination_layer
from mnms.graph.layers import SharedVehicleLayer, MultiLayerGraph
from mnms.vehicles.veh_type import Bike
from mnms.generation.demand import generate_random_demand
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.demand import CSVDemandManager
from mnms.time import TimeTable, Time, Dt
from mnms.log import set_mnms_logger_level, LOGLEVEL, attach_log_file
from mnms.io.graph import save_graph

# set_all_mnms_logger_level(LOGLEVEL.WARNING)
set_mnms_logger_level(LOGLEVEL.INFO, ["mnms.simulation"])

# get_logger("mnms.graph.shortest_path").setLevel(LOGLEVEL.WARNING)
attach_log_file('simulation.log')

##################
### Parameters ###
##################
demand_file = pathlib.Path(__file__).parent.joinpath('demand.csv').resolve()
log_file = pathlib.Path(__file__).parent.joinpath('sim.log').resolve()
n_nodes_per_dir = 5
mesh_size = 1000 # m
velov_default_speed = 3 # m/s
b_freefloating = 1
velov_dt_matching = 1
n_odnodes_x = 5
n_odnodes_y = 5
odlayer_xmin = -1000
odlayer_ymin = -1000
odlayer_xmax = 3000 # m
odlayer_ymax = 3000 # m
odlayer_connection_dist = 500 # m
def mfdspeed(dacc):
    dspeed = {'BIKE': 3}
    return dspeed
tstart = Time("07:00:00")
tend = Time("09:00:00")
dt_flow = Dt(minutes=1)
affectation_factor = 1

#########################
### Scenario creation ###
#########################

#### RoadDescriptor ####
road_db = generate_manhattan_road(n_nodes_per_dir, mesh_size, prefix='I_')

#### MLGraph ####
ff_velov = VehicleSharingMobilityService("ff_velov", b_freefloating, velov_dt_matching)
ff_velov.attach_vehicle_observer(CSVVehicleObserver("velov_vehs.csv"))
velov_layer = generate_layer_from_roads(road_db, 'velov_layer', SharedVehicleLayer, Bike, velov_default_speed, [ff_velov])

odlayer = generate_grid_origin_destination_layer(odlayer_xmin, odlayer_ymin,
    odlayer_xmax, odlayer_ymax, n_odnodes_x, n_odnodes_y)

mlgraph = MultiLayerGraph([velov_layer], odlayer)

# Add free-floating vehicle
ff_velov.init_free_floating_vehicles('I_2', 1)

# Connect od layer and velov layer
mlgraph.connect_origindestination_layers(odlayer_connection_dist)

#### Decision model ####
decision_model = DummyDecisionModel(mlgraph, outfile="paths.csv")

#### Flow motor ####
flow_motor = MFDFlowMotor(outfile="flow.csv")
flow_motor.add_reservoir(Reservoir(road_db.zones["RES"], ['BIKE'], mfdspeed))

#### Demand ####
demand = CSVDemandManager(demand_file)
demand.add_user_observer(CSVUserObserver('users.csv'))

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

supervisor.run(tstart,
               tend,
               dt_flow,
               affectation_factor)
