###############
### Imports ###
###############
## Casuals
import os
import pathlib
import pandas as pd
import math

# MnMS
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.mobility_service.vehicle_sharing import VehicleSharingMobilityService
from mnms.generation.layers import generate_layer_from_roads, generate_bbox_origin_destination_layer
from mnms.graph.layers import SharedVehicleLayer, MultiLayerGraph
from mnms.vehicles.veh_type import Bike
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.demand import CSVDemandManager
from mnms.time import Time, Dt
from mnms.log import set_mnms_logger_level, LOGLEVEL, attach_log_file
from mnms.io.graph import load_graph, load_odlayer, save_odlayer, save_transit_link_odlayer, load_transit_links
from unidecode import unidecode
from pyproj import Transformer

##################
### Parameters ###
##################
b_from_json = False
mlgraph_file = 'lyon_velov.json'
lyon_velov_csv_file = 'stations-velo-v-metropole-lyon.csv'
demand_file = pathlib.Path(__file__).parent.joinpath('fichier_demandes_10.csv').resolve()
log_file = 'sim.log'
n_nodes_per_dir = 3

velov_default_speed = 3 # m/s
b_freefloating = False
velov_dt_matching = 1

def mfdspeed(dacc):
    dspeed = {'BIKE': 3}
    return dspeed

tstart = Time("06:00:00")
tend = Time("12:00:00")
dt_flow = Dt(minutes=1)
affectation_factor = 10

NX = 100
NY = 100
#DIST_CONNECTION = 1e2


def gps_to_lambert93(lat, lon):
    # Create a transformer for EPSG:4326 (WGS84) to EPSG:5698 (Lambert 93 CC46)
    transformer = Transformer.from_crs("epsg:4326", "epsg:5698", always_xy=True)

    # Transform coordinates from WGS84 to Lambert 93
    x, y = transformer.transform(lon, lat)

    return x, y


def cleanString(string):

    clean_str = unidecode(str(''.join(i for i in string if i.isalnum())))

    return clean_str


def closest_node(nodes, x, y):
    """
    Finds the closest node to the given x, y coordinates in the graph.

    Parameters:
    - graph: The networkx graph.
    - x, y: The coordinates of the target point.

    Returns:
    - The ID of the closest node.
    """

    closest_node = None
    min_distance = float("inf")

    for id, node in nodes.items():
        # Extract the position of the current node
        node_x, node_y = node.position

        # Calculate the Euclidean distance
        distance = math.sqrt((node_x - x) ** 2 + (node_y - y) ** 2)

        # Update the closest node if a smaller distance is found
        if distance < min_distance:
            closest_node = id
            min_distance = distance

    return closest_node, min_distance


#########################
### Scenario creation ###
#########################

#### RoadDescriptor and MLGraph ####

mlgraph = load_graph(mlgraph_file)

# OD layer
odlayer = generate_bbox_origin_destination_layer(mlgraph.roads, 100, 100)
mlgraph.odlayer = odlayer
mlgraph.add_origin_destination_layer(odlayer)

# Vehicle sharing mobility service
# velov_service = VehicleSharingMobilityService("velov", b_freefloating, velov_dt_matching)
# velov_service.attach_vehicle_observer(CSVVehicleObserver("velov_vehs.csv"))

# velov_layer = generate_layer_from_roads(mlgraph.roads, "velov_layer", SharedVehicleLayer, Bike, velov_default_speed, [velov_service])

# Multilayer graph
# mlgraph.layers["velov_layer"].add_mobility_service(velov_service)
# mlgraph = MultiLayerGraph([velov_layer], odlayer)

# Velov Data
dtype = {'idstation': str}
df_velov = pd.read_csv(lyon_velov_csv_file, sep=';', dtype=dtype)
df_velov = df_velov[["idstation", "nom", "nbbornettes", "lon", "lat"]]

# Add stations
for index, velov_station in df_velov.iterrows():
    id_station = "VLV_" + cleanString(velov_station["nom"])

    lat = float(velov_station["lat"].replace(',', '.'))
    lon = float(velov_station["lon"].replace(',', '.'))
    x_coord, y_coord = gps_to_lambert93(lat, lon)

    node_station, dist = closest_node(mlgraph.roads.nodes, x_coord, y_coord)
    capacity_station = velov_station["nbbornettes"]

    mlgraph.layers['velov_layer'].mobility_services['velov'].create_station(id_station, node_station, capacity=capacity_station, nb_initial_veh=5)

# Connect od layer and velov layer
if not os.path.exists(f"transit_link_{NX}_{NY}_{500}_grid.json"):
    mlgraph.connect_origindestination_layers(500, 1000)
    save_transit_link_odlayer(mlgraph, f"transit_link_{NX}_{NY}_{500}_grid.json")
else:
    load_transit_links(mlgraph, f"transit_link_{NX}_{NY}_{500}_grid.json")

#### Decision model ####
decision_model = DummyDecisionModel(mlgraph, outfile="paths.csv")

#### Flow motor ####
flow_motor = MFDFlowMotor(outfile="flow.csv")
flow_motor.add_reservoir(Reservoir(mlgraph.roads.zones['RES'], ['BIKE'], mfdspeed))

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
