###############
### Imports ###
###############
## Casuals
import pathlib

## MnMS
from mnms.generation.roads import generate_manhattan_road
from mnms.generation.layers import generate_layer_from_roads, generate_grid_origin_destination_layer
from mnms.graph.layers import MultiLayerGraph
from mnms.demand.manager import CSVDemandManager
from mnms.log import set_all_mnms_logger_level, LOGLEVEL
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.time import Time, Dt
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver

##################
### Parameters ###
##################

demand_file = pathlib.Path(__file__).parent.joinpath('demand.csv').resolve()
log_file = pathlib.Path(__file__).parent.joinpath('sim.log').resolve()
n_nodes_per_dir = 3
mesh_size = 100  # m
n_odnodes_x = 3
n_odnodes_y = 3
odlayer_xmin = 0
odlayer_ymin = 0
odlayer_xmax = 300  # m
odlayer_ymax = 300  # m
odlayer_connection_dist = 1e-3  # m


def mfdspeed(dacc):
    dspeed = {'CAR': 3}  # m/s
    return dspeed


tstart = Time("07:00:00")
tend = Time("07:10:00")
dt_flow = Dt(seconds=10)
affectation_factor = 10

#########################
### Scenario creation ###
#########################

#### RoadDescriptor ####
road_db = generate_manhattan_road(n_nodes_per_dir, mesh_size)  # one zone automatically generated

#### MlGraph ####
personal_car = PersonalMobilityService()
personal_car.attach_vehicle_observer(CSVVehicleObserver("veh.csv"))
car_layer = generate_layer_from_roads(road_db,
                                      'CAR',
                                      mobility_services=[personal_car])

odlayer = generate_grid_origin_destination_layer(odlayer_xmin, odlayer_ymin, odlayer_xmax,
                                                 odlayer_ymax, n_odnodes_x, n_odnodes_y)

mlgraph = MultiLayerGraph([car_layer],
                          odlayer,
                          odlayer_connection_dist)

# save_graph(mlgraph, demand_file.parent.joinpath('graph.json'))

# load_graph(demand_file.parent.joinpath('graph.json'))


#### Demand ####
demand = CSVDemandManager(demand_file)
demand.add_user_observer(CSVUserObserver('user.csv'))

#### Decision model ####
decision_model = DummyDecisionModel(mlgraph, outfile="path.csv")

#### Flow motor ####
flow_motor = MFDFlowMotor('flow.csv')
flow_motor.add_reservoir(Reservoir(road_db.zones["RES"], 'CAR', mfdspeed))

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

opti = True
opti_factor = 5

if opti == True:
    supervisor.run_optimization(tstart,
                   tend,
                   dt_flow,
                   affectation_factor,
                   opti_factor)
else:
    supervisor.run(tstart,
                   tend,
                   dt_flow,
                   affectation_factor)
