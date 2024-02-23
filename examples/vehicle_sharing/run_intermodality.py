###############
### Imports ###
###############
## Casuals
import pathlib

# MnMS
from mnms.generation.roads import generate_manhattan_road
from mnms.generation.layers import generate_layer_from_roads, generate_grid_origin_destination_layer
from mnms.mobility_service.vehicle_sharing import VehicleSharingMobilityService
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.tools.observer import CSVVehicleObserver, CSVUserObserver
from mnms.graph.layers import SharedVehicleLayer, MultiLayerGraph
from mnms.vehicles.veh_type import Bike
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.demand import CSVDemandManager
from mnms.time import Time, Dt
from mnms.log import set_mnms_logger_level, LOGLEVEL, attach_log_file
from mnms.io.graph import save_graph, load_graph

##################
### Parameters ###
##################
demand_file = pathlib.Path(__file__).parent.joinpath('demand.csv').resolve()
mlgraph_file = 'intermodality_example.json'
log_file = 'sim.log'
b_from_json=False
n_nodes_per_dir = 3
mesh_size = 1000 # m
n_odnodes_x = 5
n_odnodes_y = 5
odlayer_xmin = -1000
odlayer_ymin = -1000
odlayer_xmax = 3000 # m
odlayer_ymax = 3000 # m$
b_freefloating = 0
velov_dt_matching = 1
velov_default_speed = 3 # m/s
odlayer_connection_dist = 500 # m
car_velov_connection_dist = 300 # m
def mfdspeed(dacc):
    dspeed = {'CAR':5.55, 'BIKE': 6.66}
    return dspeed
tstart = Time("06:50:00")
tend = Time("09:00:00")
dt_flow = Dt(minutes=1)
affectation_factor = 10

#########################
### Scenario creation ###
#########################

#### RoadDescriptor and MLGraph ####
if b_from_json:
    mlgraph=load_graph(mlgraph_file)

    # OD layer
    odlayer = generate_grid_origin_destination_layer(odlayer_xmin, odlayer_ymin,
        odlayer_xmax, odlayer_ymax, n_odnodes_x, n_odnodes_y)
    mlgraph.add_origin_destination_layer(odlayer)
else:
    # Graph
    road_db = generate_manhattan_road(n_nodes_per_dir, mesh_size)

    # OD layer
    odlayer = generate_grid_origin_destination_layer(odlayer_xmin, odlayer_ymin,
        odlayer_xmax, odlayer_ymax, n_odnodes_x, n_odnodes_y)

    # Personnal car mobility service
    personal_car = PersonalMobilityService()
    personal_car.attach_vehicle_observer(CSVVehicleObserver("pv_vehs.csv"))
    car_layer = generate_layer_from_roads(road_db,
                                          'car_layer',
                                          mobility_services=[personal_car])

    # Vehicle sharing mobility service
    velov = VehicleSharingMobilityService("velov", b_freefloating, velov_dt_matching)
    velov.attach_vehicle_observer(CSVVehicleObserver("velov_vehs.csv"))
    velov_layer = generate_layer_from_roads(road_db, 'velov_layer', SharedVehicleLayer, Bike, velov_default_speed, [velov])

    # Multilayer graph
    mlgraph = MultiLayerGraph([car_layer,velov_layer], odlayer)

    if not b_from_json:
        save_graph(mlgraph, mlgraph_file)

# Add stations
mlgraph.layers['velov_layer'].mobility_services['velov'].create_station('S1', '1', capacity=20, nb_initial_veh=5)
mlgraph.layers['velov_layer'].mobility_services['velov'].create_station('S2', 'SOUTH_2', capacity=20, nb_initial_veh=0)

# Connect od layer and velov layer
mlgraph.connect_origindestination_layers(odlayer_connection_dist)

# Connect personnal car layer and velov layer
mlgraph.connect_inter_layers(['car_layer','velov_layer'], car_velov_connection_dist)

#### Decision model ####
decision_model = DummyDecisionModel(mlgraph, outfile="paths.csv", verbose_file=True)

#### Flow motor ####
flow_motor = MFDFlowMotor(outfile="flow.csv")
flow_motor.add_reservoir(Reservoir(mlgraph.roads.zones['RES'], ['BIKE', 'CAR'], mfdspeed))

#### Demand ####
demand = CSVDemandManager(demand_file)
demand.add_user_observer(CSVUserObserver('users.csv'))

#### Supervisor ####
supervisor = Supervisor(mlgraph,
                         demand,
                         flow_motor,
                         decision_model)

######################
### Run simulation ###
######################

# set_all_mnms_logger_level(LOGLEVEL.WARNING)
set_mnms_logger_level(LOGLEVEL.INFO, ["mnms.simulation"])

# get_logger("mnms.graph.shortest_path").setLevel(LOGLEVEL.WARNING)
attach_log_file(log_file)

supervisor.run(tstart,
                tend,
                dt_flow,
                affectation_factor)
