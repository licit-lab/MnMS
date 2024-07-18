###############
### Imports ###
###############
## Casuals
import os
import numpy as np
import time
import json

## MnMS & HiPOP
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.simulation import Supervisor
from mnms.demand import CSVDemandManager
from mnms.flow.MFD import Reservoir, MFDFlowMotor
from mnms.log import LOGLEVEL, set_all_mnms_logger_level
from mnms.time import Time, Dt
from mnms.io.graph import load_graph, load_odlayer, save_transit_links
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.generation.layers import generate_layer_from_roads
from mnms.io.graph import load_transit_links
from mnms.graph.layers import MultiLayerGraph

##################
### Parameters ###
##################
## Parameters file
f = open('params.json')
params = json.load(f)

# Load transit links, if False create and save them
LOAD_TRANSIT = True

## Directories and files
CURRENT_DIR = str(os.path.dirname(os.path.abspath(__file__)))
INDIR = CURRENT_DIR + '/inputs/'
OUTDIR = CURRENT_DIR + '/outputs/'
LOG_FILE = OUTDIR + 'sim.log'
SERIALIZED_MLGRAPH = INDIR + params['fn_network']
SERIALIZED_ODLAYER = INDIR + params['fn_odlayer']
DEMAND_FILE = INDIR + params['fn_demand']

METROVEH_OUTFILE = OUTDIR + 'metro_veh.csv'
TRAMVEH_OUTFILE = OUTDIR + 'tram_veh.csv'
BUSVEH_OUTFILE = OUTDIR + 'bus_veh.csv'
CARVEH_OUTFILE = OUTDIR + 'car_veh.csv'
USERS_OUTFILE = OUTDIR + 'users.csv'
PATHS_OUTFILE = OUTDIR + "path.csv"
FLOW_OUTFILE = OUTDIR + "flow.csv"
fn_transit_links = INDIR + 'transit_links.json'

## Outputs writing
LOG_LEVEL = LOGLEVEL.INFO
OBSERVERS = True

## Flow dynamics parameters
#V_CAR = params['V_CAR'] # m/s
V_BUS = params['V_BUS'] # m/s
V_TRAM = params['V_TRAM'] # m/s
V_METRO = params['V_METRO'] # m/s
WALK_SPEED = 1.42 # m/s

## MultiLayerGraph creation
DIST_MAX = params['DIST_MAX'] # m
DIST_CONNECTION_OD = params['DIST_CONNECTION_OD'] # m
DIST_CONNECTION_PT = params['DIST_CONNECTION_PT'] # m
DIST_CONNECTION_MIX = params['DIST_CONNECTION_MIX'] # m

## Costs
COST_NAME = 'travel_time'

## Paths choices - # considered modes, packages, nb_paths

#considered_modes = [({'BUSLayer', 'TRAMLayer', 'METROLayer'}, None, 1),
#                    ({'CARLayer'},None,1)]
considered_modes = None

## Simulation parameters
START_TIME = Time('15:59:00')
END_TIME = Time('19:00:00')
DT_FLOW = Dt(minutes=2)
AFFECTION_FACTOR = 1

#################
### Functions ###
#################
def timed(func):
    """Decorator to measure the execution time of a function.
    """
    def decorator(*args, **kwargs):
        t1 = time.time()
        result = func(*args, **kwargs)
        t2 = time.time()
        print(f'Execution of {func.__name__} function took {t2-t1:.2f} seconds')
        return result
    return decorator

@timed
def load_mlgraph_from_serialized_data():
    mlgraph = load_graph(SERIALIZED_MLGRAPH)
    odlayer = load_odlayer(SERIALIZED_ODLAYER)
    mlgraph.add_origin_destination_layer(odlayer)
    return mlgraph

@timed
def connect_intra_and_inter_pt_layers(mlgraph):
    mlgraph.connect_inter_layers(["BUSLayer", "TRAMLayer", "METROLayer"], DIST_CONNECTION_PT,
                                    extend_connect=True, max_connect_dist=DIST_MAX)
    mlgraph.connect_intra_layer("BUSLayer", DIST_CONNECTION_PT)
    mlgraph.connect_intra_layer("TRAMLayer", DIST_CONNECTION_PT)
    mlgraph.connect_intra_layer("METROLayer", DIST_CONNECTION_PT)

# Xinyun's fit based on MATSim simulation
def calculate_V_MFD(acc, V_BUS=V_BUS, V_TRAM=V_TRAM, V_METRO=V_METRO):
    a = 2.8981940480441857
    b = -0.00010553060526140915
    V = np.exp(a + b * 10*acc["CAR"]) # factor 10 to increase congestion for PT share
    V_CAR = max(V, 0.001)  # min speed to avoid gridlock
    return {"CAR": V_CAR,"BUS": V_BUS, "TRAM": V_TRAM, "METRO": V_METRO}

@timed
def create_supervisor():
    #### MlGraph ####
    #################
    ## Load mlgraph from serialized data, it contains roads, and PT layers and mob services
    loaded_mlgraph = load_mlgraph_from_serialized_data()
    roads = loaded_mlgraph.roads
    odlayer = loaded_mlgraph.odlayer

    ## Define OBSERVERS
    metro_veh_observer = CSVVehicleObserver(METROVEH_OUTFILE) if OBSERVERS else None
    tram_veh_observer = CSVVehicleObserver(TRAMVEH_OUTFILE) if OBSERVERS else None
    bus_veh_observer = CSVVehicleObserver(BUSVEH_OUTFILE) if OBSERVERS else None
    car_veh_observer = CSVVehicleObserver(CARVEH_OUTFILE) if OBSERVERS else None

    ## Metro
    metro_layer = loaded_mlgraph.layers['METROLayer']
    metro_service = metro_layer.mobility_services['METRO']
    metro_service.attach_vehicle_observer(metro_veh_observer)

    ## Tram
    tram_layer = loaded_mlgraph.layers['TRAMLayer']
    tram_service = tram_layer.mobility_services['TRAM']
    tram_service.attach_vehicle_observer(tram_veh_observer)

    ## Bus
    bus_layer = loaded_mlgraph.layers['BUSLayer']
    bus_service = bus_layer.mobility_services['BUS']
    bus_service.attach_vehicle_observer(bus_veh_observer)

    ## Car
    car = PersonalMobilityService()
    banned_nodes = [k for k in roads.nodes.keys() if ('TRAM' in k or 'BUS' in k or 'METRO' in k)]
    banned_sections = [k for k in roads.sections.keys() if ('TRAM' in k or 'BUS' in k or 'METRO' in k)]

    car_layer = generate_layer_from_roads(roads,
                                          'CARLayer',
                                          mobility_services=[car],
                                          banned_nodes=banned_nodes,
                                          banned_sections=banned_sections)
    car.attach_vehicle_observer(car_veh_observer)


    ## MLGraph with all layers, including odlayer, do the connections between ODLayer and other layers directly
    mlgraph = MultiLayerGraph([bus_layer, tram_layer, metro_layer, car_layer],
            odlayer)

    # Add the transit links intra and inter layers
    if LOAD_TRANSIT:
        load_transit_links(mlgraph, fn_transit_links)
    else:
        connect_intra_and_inter_pt_layers(mlgraph)
        #mlgraph.connect_origindestination_layers(DIST_CONNECTION_OD)
        for l in ["BUSLayer", "TRAMLayer", "METROLayer", "CARLayer"]:
            transit_links = mlgraph.layers[l].connect_origindestination(mlgraph.odlayer, DIST_CONNECTION_OD)
            mlgraph.add_transit_links(transit_links)
        save_transit_links(mlgraph, fn_transit_links)

    #### Demand ####
    ################
    demand = CSVDemandManager(DEMAND_FILE)
    demand.add_user_observer(CSVUserObserver(USERS_OUTFILE))

    #### Decison Model ####
    #######################
    travel_decision = DummyDecisionModel(mlgraph, considered_modes=considered_modes, outfile=PATHS_OUTFILE, cost=COST_NAME)
    travel_decision.add_waiting_cost_function(COST_NAME, lambda wt: wt)

    #### Flow motor ####
    ####################
    flow_motor = MFDFlowMotor(outfile=FLOW_OUTFILE)
    flow_motor.add_reservoir(Reservoir(mlgraph.roads.zones["RES"], ["CAR", "BUS", "TRAM", "METRO"], calculate_V_MFD))

    #### Supervisor ####
    ####################
    supervisor = Supervisor(mlgraph,
                            demand,
                            flow_motor,
                            travel_decision,
                            logfile=LOG_FILE,
                            loglevel=LOG_LEVEL)

    return supervisor

@timed
def run_simulation(supervisor):
    set_all_mnms_logger_level(LOG_LEVEL)
    supervisor.run(START_TIME, END_TIME, DT_FLOW, AFFECTION_FACTOR)

############
### Main ###
############
if __name__ == '__main__':
    supervisor = create_supervisor()
    run_simulation(supervisor)
