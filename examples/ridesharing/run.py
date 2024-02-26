###############
### Imports ###
###############
## Casuals
import os
import random
import pandas as pd
import numpy as np
import time
from stepfunction import stepfunction as sf # install with pip install -i https://test.pypi.org/simple/ stepfunction-kit4a

## MnMS & HiPOP
from mnms.log import set_all_mnms_logger_level, LOGLEVEL
from mnms.generation.roads import generate_manhattan_road
from mnms.tools.observer import CSVVehicleObserver, CSVUserObserver
from mnms.mobility_service.on_demand_shared import OnDemandSharedMobilityService
from mnms.graph.layers import MultiLayerGraph
from mnms.vehicles.veh_type import Car
from mnms.time import TimeTable, Time, Dt
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.demand.manager import CSVDemandManager
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.log import LOGLEVEL


##################
### Parameters ###
##################
## Directories and files
current_dir = os.path.dirname(os.path.abspath(__file__))
outdir = str(current_dir) + '/outputs/'
indir = str(current_dir) + '/inputs/'
demand_file = indir + 'demand.csv'
ridesharing_vehicles_init_positions_file = indir + 'ridesharing_vehicles_initial_positions.csv'
log_file = outdir + 'sim.log'
paths_file = outdir + 'paths.csv'
vehs_file = outdir + 'vehs.csv'
users_file = outdir + 'users.csv'

# Ride-sharing parameters
ridesharing_dt_matching = 4 # matching step = ridesharing_dt_matching * flow_dt
radius = 2000 # m
ridesharing_veh_cap = 3
default_waiting_time = 0 # s
matching_strategy = 'smallest_disutility_vehicle_in_radius_fifo'
replanning_strategy = 'all_pickups_first_fifo'
nb_ridesharing_vehs = 200

# Default speeds
vehs_default_speed = 11.5 # m/s

# MultiLayerGraph creation
graph_mesh_size = 500
graph_nb_nodes_1dim = 15
max_access_egress_dist = 100 # m, distance used to connect ODLayer to other layers

# Demand
dep_rates = [[0, 1800, 3600],[0.9,1.4,0.5]] # s and dep/s
first_dep_time = Time('07:00:00')
last_dep_time = Time('08:00:00')
u_params = {'max_detour_ratio': 1.5}

# Scenario
tstart = Time('06:55:00') # start flow_dt * affectation_factor before first departure to let the graph be updated before first travel choice
tend = Time('08:05:00')
flow_dt = Dt(seconds=30)
affectation_factor = 10

#################
### Functions ###
#################
def generate_ridesharing_vehicles_init_pos_f(rs, nb_vehs, file):
    """Randomly generates a set of initial positions for ride-sharing vehciles.

    Args:
        - rs: ride-sharing mobility service
        - nb_vehs: number of vehicles to generate
        - file: file where initial positions should be written
    """
    vehs = []
    possible_nodes = list(rs.layer.graph.nodes.keys())
    for i in range(nb_vehs):
        # Draw a random node where veh starts
        node = random.choice(possible_nodes)
        vehs.append([node])
    rs_supply = pd.DataFrame(vehs, columns=['NODE'])
    if not os.path.isfile(file):
        rs_supply.to_csv(file, sep=';', index=False)
    else:
        print(f"A ridesharing initial positions file already exist. Nothing is generated to prevent overwriting.")

def generate_demand_scenario(mlgraph, dep_rates, tstart, tend, demand_file):
    """Generates a randomized demand scenario and write it down in a file.

    Args:
        - mlgraph
        - dep_rates: [[t0,t1,t2],[dpr1,dpr2,dpr3]] where intervals t0,t1,t2 are in
                     seconds, values dpr1,dpr2,dpr3 designate the number of departures
                     per second on the intervals
        - tstart: time at which departures start
        - tend: time at which departures stop
        - demand_file: file where to write the demand
    """
    t = 0
    dep_rates = sf.PiecewiseConstantFunction(dep_rates[0], dep_rates[1])
    uid = 0
    travelers = []
    nodes = list(mlgraph.graph.nodes.keys())
    while True:
        dep_rate = dep_rates.get(t)
        t += random.expovariate(dep_rate)
        if tstart.add_time(Dt(seconds=t)) >= tend:
            break
        while True:
            # Choose random origin and destination nodes
            opos = mlgraph.graph.nodes[random.choice(nodes)].position
            dpos = mlgraph.graph.nodes[random.choice(nodes)].position

            if opos[0] != dpos[0] and opos[1] != dpos[1]:
                travelers.append(['U'+str(uid), tstart.add_time(Dt(seconds=round(t,0))), str(opos[0])+' '+str(opos[1]),
                    str(dpos[0])+' '+str(dpos[1])])
                uid += 1
                break
    df = pd.DataFrame(travelers, columns=['ID', 'DEPARTURE', 'ORIGIN', 'DESTINATION'])

    if not os.path.isfile(demand_file):
        df.to_csv(demand_file, sep=';', index=False)
    else:
        print(f"A demand file already exist. Nothing is generated to prevent overwriting.")

def create_on_demand_vehicles(on_demand_mob_service, vehicles_positions_file):
    """Create the on-demand vehicles at the initial positions specified by the file.

    Args:
        - on_demand_mob_service: the on demand mobility service object
        - vehicles_positions_file: the file where initial positions are specified
    """
    with open(vehicles_positions_file, 'r'):
        df = pd.read_csv(vehicles_positions_file, delimiter=';', quotechar='|')
        [on_demand_mob_service.create_waiting_vehicle(n) for n in df.NODE]

def create_supervisor(observers=True, generate_ridesharing_vehicles_init_pos=True, generate_demand=True):
    """Creates a supervisor.

    Args:
        - observers: specifies if observers for users, and vehicles should be initiated
        - generate_ridesharing_vehicles_init_pos: specifies if a new initial positioning for
                                                 ride-hailing vehicles should be generated
        - generate_demand: specifies if a new demand scenario should be generated

    Returns:
        -supervisor
    """

    #### RoadDescriptor ####
    ########################
    roads = generate_manhattan_road(graph_nb_nodes_1dim, graph_mesh_size, extended=False)

    #### MlGraph ####
    #################
    ## Observers
    vehs_observer = CSVVehicleObserver(vehs_file) if observers else None
    uberpool = OnDemandSharedMobilityService('UBERPOOL', ridesharing_veh_cap, ridesharing_dt_matching, 0, default_waiting_time=default_waiting_time,
        matching_strategy=matching_strategy, replanning_strategy=replanning_strategy,
        radius=radius)
    ridesharing_layer = generate_layer_from_roads(roads, 'RIDESHARING', mobility_services=[uberpool])
    uberpool.attach_vehicle_observer(vehs_observer)
    # Generate random initial positionning if needed
    if generate_ridesharing_vehicles_init_pos:
        generate_ridesharing_vehicles_init_pos_f(uberpool, nb_ridesharing_vehs, ridesharing_vehicles_init_positions_file)
    create_on_demand_vehicles(uberpool, ridesharing_vehicles_init_positions_file)

    # OD
    od_layer = generate_matching_origin_destination_layer(roads, with_stops=False)

    # ML graph
    mlgraph = MultiLayerGraph([ridesharing_layer], od_layer, max_access_egress_dist)

    #### Demand ####
    ################
    if generate_demand:
        generate_demand_scenario(mlgraph, dep_rates, first_dep_time, last_dep_time, demand_file)
    demand = CSVDemandManager(demand_file, user_parameters=lambda u, u_params=u_params: u_params)
    if observers:
        demand.add_user_observer(CSVUserObserver(users_file))

    #### Decison Model ####
    #######################
    decision_model = DummyDecisionModel(mlgraph, outfile=paths_file, verbose_file=True)

    #### Flow motor ####
    ####################
    def mfdspeed(dacc):
        dspeed = {'CAR': 10}
        return dspeed

    flow_motor = MFDFlowMotor()
    flow_motor.add_reservoir(Reservoir(roads.zones["RES"], ['CAR'], mfdspeed))

    #### Supervisor ####
    ####################
    #save_graph(mlgraph, str(current_dir) + '/inputs/mlgraph.json')
    supervisor = Supervisor(mlgraph,
                        demand,
                        flow_motor,
                        decision_model,
                        logfile=log_file,
                        loglevel=LOGLEVEL.INFO)

    return supervisor

############
### Main ###
############
if __name__ == '__main__':
    set_all_mnms_logger_level(LOGLEVEL.INFO)

    supervisor = create_supervisor() # Do not forget to create inputs and outputs dir and
                                     # generate the inputs first time you lanch this script !
    st = time.time()
    supervisor.run(tstart, tend, flow_dt, affectation_factor)
    print(f'Run time = {time.time() - st}')
