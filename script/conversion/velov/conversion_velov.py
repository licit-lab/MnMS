###############
### Imports ###
###############
## Casuals
import pandas as pd
import math

# MnMS
from mnms.mobility_service.vehicle_sharing import VehicleSharingMobilityService

from mnms.generation.layers import generate_layer_from_roads
from mnms.graph.layers import SharedVehicleLayer, MultiLayerGraph
from mnms.vehicles.veh_type import Bike
from mnms.io.graph import load_graph, save_graph
from unidecode import unidecode
from pyproj import Transformer


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


##################
### Parameters ###
##################

mnms_json_filepath = 'lyon_roads.json'
lyon_velov_csv_file = 'stations-velo-v-metropole-lyon.csv'
mlgraph_dump_file = 'lyon_velov.json'

velov_default_speed = 3 # m/s
b_freefloating = False
velov_dt_matching = 1


def mfdspeed(dacc):
    dspeed = {'BIKE': 3}
    return dspeed


#### RoadDescriptor and MLGraph ####

# Graph
mnms_graph = load_graph(mnms_json_filepath)
roads = mnms_graph.roads


# Velov Data
dtype = {'idstation': str}
df_velov = pd.read_csv(lyon_velov_csv_file, sep=';', dtype=dtype)
df_velov = df_velov[["idstation", "nom", "nbbornettes", "lon", "lat"]]


# Vehicle sharing mobility service
velov = VehicleSharingMobilityService("velov", b_freefloating, velov_dt_matching)
velov_layer = generate_layer_from_roads(roads, 'velov_layer', SharedVehicleLayer,
    Bike, velov_default_speed, [velov])


# Multilayer graph
mlgraph = MultiLayerGraph([velov_layer], None, None)


# Add stations
for index, velov_station in df_velov.iterrows():
    id_station = "VLV_" + cleanString(velov_station["nom"])

    lat = float(velov_station["lat"].replace(',', '.'))
    lon = float(velov_station["lon"].replace(',', '.'))
    x_coord, y_coord = gps_to_lambert93(lat, lon)

    node_station, dist = closest_node(mlgraph.roads.nodes, x_coord, y_coord)
    capacity_station = velov_station["nbbornettes"]

    mlgraph.layers['velov_layer'].mobility_services['velov'].create_station(id_station, node_station, capacity=capacity_station, nb_initial_veh=5)


save_graph(mlgraph, mlgraph_dump_file)


