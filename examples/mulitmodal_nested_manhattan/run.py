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
from mnms.generation.roads import generate_nested_manhattan_road
from transit_network_generation import generate_daganzo_hybrid_transit_network_stops, generate_daganzo_hybrid_transit_network_lines
from mnms.generation.zones import generate_grid_zones
from mnms.tools.observer import CSVVehicleObserver, CSVUserObserver
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.graph.layers import MultiLayerGraph, PublicTransportLayer
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.on_demand import OnDemandMobilityService
from mnms.vehicles.veh_type import Bus, Metro, Car, Train
from mnms.time import TimeTable, Time, Dt
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from layers_connection import connect_layers
from mnms.demand.manager import CSVDemandManager
from mnms.graph.zone import MLZone
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.travel_decision.logit import LogitDecisionModel, ModeCentricLogitDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.log import LOGLEVEL

##################
### Parameters ###
##################
## Directories and files
current_dir = os.path.dirname(os.path.abspath(__file__))
outdir = str(current_dir) + '/outputs/'
demand_file = str(current_dir) + '/inputs/demand.csv'
ridehailing_vehicles_init_positions_file1 = str(current_dir) + '/inputs/ridehailing_vehicles_initial_positions1.csv'
ridehailing_vehicles_init_positions_file2 = str(current_dir) + '/inputs/ridehailing_vehicles_initial_positions2.csv'
zones_file = str(current_dir) + '/inputs/mlzones.csv'
mobility_services_events_graphs_file = str(current_dir) + '/inputs/mobility_services_events_graphs.json'
log_file = outdir + 'sim.log'
paths_file = outdir + 'paths.csv'
ptveh_file = outdir+ 'pt_veh.csv'
carveh_file = outdir+ 'car_veh.csv'
rhveh_file = outdir+ 'ridehailing_veh.csv'
user_file = outdir + 'user.csv'

# PT network frequencies
metro_freq = 6 # min
bus_freq = 10 # min
feederbus_freq = 15 # min
train_freq = 20 # min

# Ride-hailing parameters
ridehailing_dt_matching = 3 # min
nb_ridehailing_vehs1 = 200
nb_ridehailing_vehs2 = 200

# Reservoirs
nb_res_x = 3
nb_res_y = 3
Vmaxs = {'RES_0-0': 15.5, 'RES_0-1': 15.5, 'RES_0-2': 15.5,
     'RES_1-0': 15.5, 'RES_1-1': 11.5, 'RES_1-2': 15.5,
     'RES_2-0': 15.5, 'RES_2-1': 15.5, 'RES_2-2': 15.5} # should be consistent with nb of reservoirs !
Vmetro = 13 # m/s
Vtrain = 18 # m/s
# Function definition should be consistent with vehicle types used in the scenario !
def mfdspeed_function_def(L, Vmax, Vmetro=Vmetro, Vtrain=Vtrain):
    def mfdspeed(dacc, L=L, Vmax=Vmax, Vmetro=Vmetro, Vtrain=Vtrain):
        Nmax = L / 10
        Nc1 = Nmax * 0.225
        Vc1 = Vmax * 0.5
        Nc2 = Nmax * 0.6875
        Vc2 = Vmax * 0.4
        Vc3 = Vmax * 0.1
        N = dacc['CAR'] + dacc['BUS']
        V = 0  # data from fit dsty
        if N < Nc1:
            V = Vmax-N*Vc1/Nc1
        elif N < Nc2:
            V = Vmax-Vc1-(N-Nc1)*Vc2/(Nc2-Nc1)
        elif N < Nmax:
            V = Vmax-Vc1-Vc2-(N-Nc2)*Vc3/(Nmax-Nc2)
        V = max(V, 0.001)  # min speed to avoid gridlock
        return {'CAR': V, 'BUS': V, 'METRO': Vmetro, 'TRAIN': Vtrain}
    return mfdspeed

# Zoning
nb_zones_x = 3
nb_zones_y = 3

# Default speeds
traditional_vehs_default_speed = 11.5 # m/s
metro_default_speed = 13 # m/s
train_default_speed = 18 # m/s

# MultiLayerGraph creation
max_access_egress_dist = 500 # m, distance used to connect ODLayer to other layers
max_transfer_dist = 200 # m, max transfer distance (from one pt line to another,
                        #    from parking to a transit stop, from dropoff spot to a pt station
                        #    from a pt station to a pickup spot)
personal_mob_service_park_radius = 100 # m, radius around user's personal veh parking location in which
                                       # she can still have access to her vehicle
banned_nodes = ['Rail_1', 'Rail_2', 'Rail_3', 'Rail_4', 'Rail_5', 'Rail_6', 'Rail_7',
    'Rail_8', 'Rail_9', 'Rail_10', 'Rail_11', 'Rail_12', 'Rail_13'] # we don't want cars, buses, metros to run there
banned_sections = ['Rail_1_Rail_2', 'Rail_2_Rail_3', 'Rail_3_Rail_4', 'Rail_4_Rail_5',
    'Rail_5_Rail_6', 'Rail_6_Rail_7', 'Rail_7_Rail_6', 'Rail_6_Rail_5', 'Rail_5_Rail_4',
    'Rail_4_Rail_3', 'Rail_3_Rail_2', 'Rail_2_Rail_1', 'Rail_8_Rail_9', 'Rail_9_Rail_10',
    'Rail_10_Rail_4', 'Rail_4_Rail_11', 'Rail_11_Rail_12', 'Rail_12_Rail_13', 'Rail_13_Rail_12',
    'Rail_12_Rail_11', 'Rail_11_Rail_4', 'Rail_4_Rail_10', 'Rail_10_Rail_9', 'Rail_9_Rail_8'] # we don't want cars, buses, metros to run there

# Demand
dep_rates = [[0, 1800, 3600],[0.9,1.4,0.5]] # s and dep/s
probas = {'#0-0': {'origin': 0.0875, 'destination': 0.0625},
          '#0-1': {'origin': 0.0875, 'destination': 0.0625},
          '#0-2': {'origin': 0.0875, 'destination': 0.0625},
          '#1-0': {'origin': 0.0875, 'destination': 0.0625},
          '#1-1': {'origin': 0.3, 'destination': 0.5},
          '#1-2': {'origin': 0.0875, 'destination': 0.0625},
          '#2-0': {'origin': 0.0875, 'destination': 0.0625},
          '#2-1': {'origin': 0.0875, 'destination': 0.0625},
          '#2-2': {'origin': 0.0875, 'destination': 0.0625}} # should be consistent with zoning parameters !
available_ms_stats = {'CAR METRO BUS RIDEHAILING TRAIN': 0.88, 'METRO BUS RIDEHAILING TRAIN': 0.12} # define proportion of users having a car
msevents_graph_stats = {'G1': 0.88, 'G2': 0.12} # define proportion of users using graphs G1 and G2
first_dep_time = Time('07:00:00')
last_dep_time = Time('08:00:00')
decision_model_type = 'dummy'
logit_theta = 0.75
considered_modes = [({'CAR', 'RIDEHAILING', 'BUS', 'METRO', 'TRAIN'}, None, 2),
                    ({'CAR'},None,2),
                    ({'BUS', 'METRO', 'TRAIN'}, None, 2),
                    ({'RIDEHAILING'}, None, 2),
                    ({'BUS', 'METRO', 'TRAIN', 'RIDEHAILING'}, ({'RIDEHAILING'}, {'BUS', 'METRO', 'TRAIN'}), 1)]

# Scenario
tstart = Time('06:55:00') # start flow_dt * affectation_factor before first departure to let the graph be updated before first travel choice
tend = Time('08:05:00')
flow_dt = Dt(seconds=30)
affectation_factor = 10
seed = 123


#################
### Functions ###
#################
def create_supervisor(observers=True, generate_ridehailing_vehicles_init_pos=False, generate_zones=False, generate_demand=False, generate_demand_graph=False):
    """Creates a supervisor.

    Args:
        - observers: specifies of observers for users, and vehicles should be initiated
        - generate_ridehailing_vehicles_init_pos: specifies if a new initial positioning for
                                                 ride-hailing vehicles should be generated
        - generate_zones: specifies if a new zoning of the MultiLayerGraph should be generated
        - generate_demand: specifies if a new demand scenario should be generated using available_ms_stats
        - generate_demand_graph: specifies if a new demand scenario should be generated using msevents_graph_stats

    Returns:
        -supervisor
    """

    #### RoadDescriptor ####
    ########################
    # Nested manhattan road network without reservoir for now
    roads = generate_nested_manhattan_road([15, 14, 12], [2000, 1000, 500], create_one_zone=False)
    # Danganzo hybrid transit network stops
    generate_daganzo_hybrid_transit_network_stops(roads) # NB: transit network is hardcoded and consistent
                                                         #     with 30x30km^2 nested Manhattan roads
    # Build reservoirs
    reservoirs = generate_grid_zones('RES_', roads, nb_res_x, nb_res_y)
    for res in reservoirs:
        roads.add_zone(res)


    #### MlGraph ####
    #################
    ## Observers
    pt_veh_observer = CSVVehicleObserver(ptveh_file) if observers else None
    car_veh_observer = CSVVehicleObserver(carveh_file) if observers else None
    ridehailing_veh_observer = CSVVehicleObserver(rhveh_file) if observers else None

    ## Public Transportation
    # Bus
    bus_service = PublicTransportMobilityService('BUS')
    bus_layer = PublicTransportLayer(roads, 'BUS', Bus, traditional_vehs_default_speed,
        services=[bus_service], observer=pt_veh_observer)
    # Metro
    metro_service = PublicTransportMobilityService('METRO')
    metro_layer = PublicTransportLayer(roads, 'METRO', Metro, metro_default_speed,
        services=[metro_service], observer=pt_veh_observer)
    # Train
    train_service = PublicTransportMobilityService('TRAIN')
    train_layer = PublicTransportLayer(roads, 'TRAIN', Train, train_default_speed,
        services=[train_service], observer=pt_veh_observer)
    # Danganzo hybrid transit network lines
    generate_daganzo_hybrid_transit_network_lines(bus_layer, metro_layer, train_layer,
        bus_freq, feederbus_freq, metro_freq, train_freq)

    ## Personal car
    personal_car = PersonalMobilityService('CAR')
    personal_car.attach_vehicle_observer(car_veh_observer)
    # As cars cannot run on the sections and nodes associated with the railways, provide banned nodes and sections
    car_layer = generate_layer_from_roads(roads, 'CAR', mobility_services=[personal_car], default_speed=traditional_vehs_default_speed,
        banned_nodes=banned_nodes, banned_sections=banned_sections)

    ## Ride-hailing
    ridehailing_service1 = OnDemandMobilityService('RIDEHAILING1', ridehailing_dt_matching) # company 1
    ridehailing_service2 = OnDemandMobilityService('RIDEHAILING2', ridehailing_dt_matching) # company 2
    ridehailing_service1.attach_vehicle_observer(ridehailing_veh_observer)
    ridehailing_service2.attach_vehicle_observer(ridehailing_veh_observer)
    # As RH vehicles cannot run on the sections and nodes associated with the railways, provide banned nodes and sections
    ridehailing_layer = generate_layer_from_roads(roads, 'RIDEHAILING', veh_type=Car,
        mobility_services=[ridehailing_service1, ridehailing_service2],
        default_speed=traditional_vehs_default_speed,
        banned_nodes=banned_nodes, banned_sections=banned_sections)
    if generate_ridehailing_vehicles_init_pos:
        generate_ridehailing_vehicles_init_pos_f(ridehailing_service1, nb_ridehailing_vehs1, ridehailing_vehicles_init_positions_file1)
        generate_ridehailing_vehicles_init_pos_f(ridehailing_service2, nb_ridehailing_vehs2, ridehailing_vehicles_init_positions_file2)
    create_on_demand_vehicles(ridehailing_service1, ridehailing_vehicles_init_positions_file1)
    create_on_demand_vehicles(ridehailing_service2, ridehailing_vehicles_init_positions_file2)

    # OD
    od_layer = generate_matching_origin_destination_layer(roads, with_stops=False)

    # ML graph
    mlgraph = MultiLayerGraph([car_layer, bus_layer, metro_layer, train_layer, ridehailing_layer], od_layer, max_access_egress_dist)

    # Add other transit links to enable intemrodality
    connect_layers(mlgraph, max_transfer_dist, personal_mob_service_park_radius)

    # Zoning
    if generate_zones:
        generate_mlzones('#', mlgraph, nb_zones_x, nb_zones_y, zones_file)
    create_mlzones(mlgraph, zones_file)


    #### Demand ####
    ################
    if generate_demand:
        generate_demand_scenario(mlgraph, dep_rates, first_dep_time, last_dep_time, probas, available_ms_stats, demand_file, 'MOBILITY SERVICES')
    elif generate_demand_graph:
        generate_demand_scenario(mlgraph, dep_rates, first_dep_time, last_dep_time, probas, msevents_graph_stats, demand_file, 'MOBILITY SERVICES GRAPH')
    demand = CSVDemandManager(demand_file)
    if observers:
        demand.add_user_observer(CSVUserObserver(user_file))


    #### Decison Model ####
    #######################
    if decision_model_type == 'dummy':
        decision_model = DummyDecisionModel(mlgraph, outfile=paths_file, verbose_file=True,
            considered_modes=considered_modes, personal_mob_service_park_radius=personal_mob_service_park_radius)
    elif decision_model_type == 'logit':
        decision_model = LogitDecisionModel(mlgraph, theta=logit_theta, outfile=paths_file, verbose_file=True,
            considered_modes=considered_modes, personal_mob_service_park_radius=personal_mob_service_park_radius)
    elif decision_model_type == 'modecentriclogit':
        decision_model = ModeCentricLogitDecisionModel(mlgraph, considered_modes, theta=logit_theta, outfile=paths_file, verbose_file=True,
            personal_mob_service_park_radius=personal_mob_service_park_radius)
    else:
        raise ValueError(f'Unknown decision model: {decision_model_type}')
    decision_model.load_mobility_services_graphs_from_file(mobility_services_events_graphs_file)


    #### Flow motor ####
    ####################
    flow_motor = MFDFlowMotor()
    for res in reservoirs:
        L = sum([roads.sections[s].length for s in res.sections])
        Vmax = Vmaxs[res.id]
        mfdspeed = mfdspeed_function_def(L, Vmax)
        flow_motor.add_reservoir(Reservoir(roads.zones[res.id], ['CAR', 'BUS', 'METRO', 'TRAIN'], mfdspeed))

    #### Supervisor ####
    ####################
    supervisor = Supervisor(mlgraph,
                        demand,
                        flow_motor,
                        decision_model,
                        logfile=log_file,
                        loglevel=LOGLEVEL.INFO)

    return supervisor


def create_on_demand_vehicles(on_demand_mob_service, vehicles_positions_file):
    """Create the on-demand vehicles at the initial positions specified by the file.

    Args:
        - on_demand_mob_service: the on demand mobility service object
        - vehicles_positions_file: the file where initial positions are specified
    """
    with open(vehicles_positions_file, 'r'):
        df = pd.read_csv(vehicles_positions_file, delimiter=';', quotechar='|')
        [on_demand_mob_service.create_waiting_vehicle(n) for n in df.NODE]


def generate_ridehailing_vehicles_init_pos_f(rh, nb_vehs, file, banned_nodes=[]):
    """Randomly generates a set of initial positions for ride-hailing vehciles.

    Args:
        - rh: ride-hailing mobility service
        - nb_vehs: number of vehicles to generate
        - file: file where initial positions should be written
        - banned_nodes: eventual nodes of the MultiLayerGraph where not to generate
                       an initial position
    """
    vehs = []
    possible_nodes = [n for n in rh.layer.graph.nodes.keys() if n not in banned_nodes]
    for i in range(nb_vehs):
        # Draw a random node where veh starts
        node = random.choice(possible_nodes)
        vehs.append([node])
    rh_supply = pd.DataFrame(vehs, columns=['NODE'])
    if not os.path.isfile(file):
        rh_supply.to_csv(file, sep=';', index=False)
    else:
        print(f"A ridehailing initial positions file already exist. Nothing is generated to prevent overwriting.")

def generate_mlzones(zid_prefix, mlgraph, Nx, Ny, zones_file):
    """Generates a grid zoning on the MultiLayerGraph.

    Args:
        - zid_prefix: Prefix for the zone id
        - mlgraph: MultiLayerGraph
        - Nx: number of zones to create along x axis
        - Ny: number of zones to create along y axis
    """
    zones = generate_grid_zones(zid_prefix, None, Nx, Ny, mlgraph=mlgraph)
    zones_ = []
    for z in zones:
        zones_.append([z.id, ' '.join(z.links), z.contour])
    df_zones = pd.DataFrame(zones_, columns=['IDS', 'LINKS', 'CONTOURS'])
    if not os.path.isfile(zones_file):
        df_zones.to_csv(zones_file, sep=';', index=False)
    else:
        print(f"A zones file already exist. Nothing is generated to prevent overwriting.")

def create_mlzones(mlgraph, file):
    with open(file, 'r'):
        df = pd.read_csv(file, delimiter=';', quotechar='|')
        for row in df.iterrows():
            id = row[1]['IDS']
            links = row[1]['LINKS'].split(' ')
            mlgraph.add_zone(MLZone(id, links, None))

def generate_demand_scenario(mlgraph, dep_rates, tstart, tend, proba, stats, demand_file, optional_column):
    """Generates a demand scenario based on the MultiLayerGraph zoning and write it down in a file.

    Args:
        - mlgraph
        - dep_rates: [[t0,t1,t2],[dpr1,dpr2,dpr3]] where intervals t0,t1,t2 are in
                     seconds, values dpr1,dpr2,dpr3 designate the number of departures
                     per second on the intervals
        - tstart: time at which departures start
        - tend: time at which departures stop
        - proba: {'zone_name': {'origin': a, 'destination': b}, ...} where a/b designate the
                 probability of drawing an origin/destination in the zone named zone_name
        - stats: {'available mob services': percentage of travelers having access to this set of mob services}
                 or {'graph_name': percentage of travelers using this mobility services events graph}
        - demand_file: file where to write the demand
        - optional_column: name of the optional columnsn, can be either 'MOBILITY SERVICES' or
                           'MOBILITY SERVICES GRAPH'
    """
    t = 0
    dep_rates = sf.PiecewiseConstantFunction(dep_rates[0], dep_rates[1])
    uid = 0
    travelers = []
    zones = list(proba.keys())
    car_nodes_per_zone = {zid: [mlgraph.graph.links[l].upstream for l in mlgraph.zones[zid].links if mlgraph.graph.links[l].label == 'CAR'] for zid in zones}
    assert len(zones) == len(mlgraph.zones.keys()) and set(zones) == set(mlgraph.zones.keys()), \
        f"All zones should have a probability associated."
    assert sum([proba[z]['origin'] for z in zones]) == 1 and sum([proba[z]['destination'] for z in zones]), \
        f"Sum of origin (resp. destination) probas should be equal to 1. "
    while True:
        dep_rate = dep_rates.get(t)
        t += random.expovariate(dep_rate)
        if tstart.add_time(Dt(seconds=t)) >= tend:
            break
        while True:
            # Choose a random origin pricing zone based on proba
            ozidx = np.random.choice(len(zones), 1, p=[proba[z]['origin'] for z in zones])[0]
            ozname = zones[ozidx]
            # Choose a random origin node position within the chosen pricing zone
            oznodes = car_nodes_per_zone[ozname]
            opos = mlgraph.graph.nodes[random.choice(oznodes)].position

            # Choose a random destination pricing zone based on proba
            dzidx = np.random.choice(len(zones), 1, p=[proba[z]['destination'] for z in zones])[0]
            dzname = zones[dzidx]
            # Choose a random origin node position within the chosen pricing zone
            dznodes = car_nodes_per_zone[dzname]
            dpos = mlgraph.graph.nodes[random.choice(dznodes)].position

            if opos[0] != dpos[0] and opos[1] != dpos[1]:
                travelers.append(['U'+str(uid), tstart.add_time(Dt(seconds=round(t,0))), str(opos[0])+' '+str(opos[1]),
                    str(dpos[0])+' '+str(dpos[1]), None])
                uid += 1
                break
    df = pd.DataFrame(travelers, columns=['ID', 'DEPARTURE', 'ORIGIN', 'DESTINATION', optional_column])
    ## Set the available mobility services / ms events graphs
    # Randomly draw the specified percentage of users for each mobility service group
    unassigned_users = list(df['ID'])
    for i,(ms_group,percentage) in enumerate(stats.items()):
        if i == len(stats)-1:
            nb_users = len(unassigned_users)
        else:
            nb_users = min(int(percentage * len(df)), len(unassigned_users))
        selected_users = random.sample(unassigned_users, nb_users)
        df.loc[df['ID'].isin(selected_users), optional_column] = ms_group
        unassigned_users = [u for u in unassigned_users if u not in selected_users]
    assert len(unassigned_users) == 0, f'Forgot to define available mobility service of users {unassigned_users}'

    if not os.path.isfile(demand_file):
        df.to_csv(demand_file, sep=';', index=False)
    else:
        print(f"A demand file already exist. Nothing is generated to prevent overwriting.")


############
### Main ###
############
if __name__ == '__main__':
    set_all_mnms_logger_level(LOGLEVEL.INFO)


    supervisor = create_supervisor(observers=True, generate_ridehailing_vehicles_init_pos=True, generate_zones=True,
                          generate_demand=True, generate_demand_graph=False)

    #supervisor = create_supervisor() # Do not forget to create inputs and outputs dir and
                                     # generate the inputs first time you lanch this script !
    st = time.time()
    supervisor.run(tstart, tend, flow_dt, affectation_factor, seed=seed)
    print(f'Run time = {time.time() - st}')
