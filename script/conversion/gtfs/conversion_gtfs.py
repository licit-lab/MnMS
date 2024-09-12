### WORK IN PROGRESS ###

###############
### Imports ###
###############

import numpy as np

from gtfs_functions import Feed
from unidecode import unidecode
from coordinates import gps_to_lambert93
from mnms.graph.layers import PublicTransportLayer, MultiLayerGraph
from mnms.vehicles.veh_type import Tram, Metro, Bus
from mnms.generation.zones import generate_one_zone
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import TimeTable, Time
from mnms.io.graph import load_graph, save_graph


##################
### Parameters ###
##################

gtfs_path = "lyon_tcl.zip" # gtfs zip folder
mnms_json_filepath = "lyon_roads.json" # mlgraph with the road network only

mlgraph_dump_file = "lyon_mnms_gtfs.json"

# Default speeds
traditional_vehs_default_speed = 13.8 # m/s
metro_default_speed = 15 # m/s
tram_default_speed = 18 # m/s


#################
### Functions ###
#################

_norm = np.linalg.norm


def cleanString(string):

    clean_str = unidecode(str(''.join(i for i in string if i.isalnum())))

    return clean_str


def secondsToMnMsTime(seconds):

    mnms_time = Time.from_seconds_24h(seconds)

    return mnms_time


def getLongestTripStops(route_merged_data):

    # Select the longest trip in route
    longest_trip_id = ""
    longest_stops_count = 0

    for index, md in route_merged_data.iterrows():
        trip_id = md["trip_id"]
        stops_count = route_merged_data["trip_id"].value_counts()[trip_id]
        if stops_count > longest_stops_count:
            longest_trip_id = trip_id
            longest_stops_count = stops_count

    # Selecting distinct stop_id and stop_name
    merged_stops = route_merged_data[
        ['stop_id', 'stop_name_y', 'trip_id', 'stop_sequence', 'stop_lat_y', 'stop_lon_y', 'geometry_y']]
    distinct_stops = merged_stops.loc[merged_stops["trip_id"] == longest_trip_id]
    distinct_stops = distinct_stops.sort_values(["stop_sequence"])
    distinct_stops = distinct_stops.reset_index()

    return distinct_stops


def extract_gtfs_stops(routes_, stops_, stop_times_, trips_, route_type):

    # Init the list of lines
    list_lines = []

    for index, route in routes_.iterrows():

        route_type_ = route["route_type"]
        route_id = route["route_id"]
        route_short_name = cleanString(route["route_short_name"])

        if route_type_ == route_type:
            ftrips = trips_.loc[trips_["route_id"] == route_id]

            # Performing the equivalent of INNER JOINs on trips with stop_times and stops
            route_merged_data = ftrips.merge(stop_times_, on='trip_id').merge(stops_, on='stop_id')

            # Selecting distinct stop_id and stop_name
            distinct_stops = getLongestTripStops(route_merged_data)
            distinct_stops["route_short_name"] = route_short_name

            # Seperate the two directions of this line
            # NB: this part of the code supposes that the second stop in one direction and the penultimate stop in the other direction are the same !
            df_line_dir1 = distinct_stops.copy()
            df_line_dir1["route_short_name"] = df_line_dir1["route_short_name"].astype(str) + "_DIR1"

            df_line_dir2 = distinct_stops.sort_values(["stop_sequence"], ascending=False)
            df_line_dir2["route_short_name"] = df_line_dir2["route_short_name"].astype(str) + "_DIR2"
            df_line_dir2 = df_line_dir2.reset_index()

            # Append two lines, one per direction
            list_lines.append(df_line_dir1)
            list_lines.append(df_line_dir2)

    return list_lines


def generate_public_transportation_lines(stop_times_, layer, list_lines, prefix_line_name):
    """Function that generates public transportation lines on a layer with a certain frequency.

    Args:
    - layer: the layer on which the lines should be created
    - list_lines: list the lines to create, one line is represented by a dataframe with LINE_ID, STOP_NAME, and STOP_CODE as columns
    - freq: frequency to apply on the lines created, shoud be a Dt type object
    - operation_start_time: time at which the timetables should start, str
    - operation_end_time: time at which the timetables should end, str
    - prefix_line_name: str corresponding to the prefix to add to the line id to name the line

    Returns:
    None
    """

    for line in list_lines:
        if not line.empty:
            line_id = line.iloc[0]['route_short_name']
            line_name = prefix_line_name + line_id

            stops = [line_name + '_' + cleanString(stp) for stp in list(line["stop_name_y"])]
            sections = [[line_name + f'_{ind}_{ind+1}', line_name + f'_{ind+1}_{ind+2}'] for ind in list(line.index)[:-2]] + [[line_name + f'_{line.index[-2]}_{line.index[-1]}']]

            first_stop_id = line.iloc[0]['stop_id']

            departure_times = stop_times_[stop_times_["stop_id"] == first_stop_id]
            departure_list = list(departure_times["departure_time"])

            time_list = [secondsToMnMsTime(departure) for departure in departure_list]
            sorted_time_list = [secondsToMnMsTime(departure) for departure in sorted(departure_list)]

            timetable = TimeTable(time_list)
            sorted_timetable = TimeTable(sorted_time_list)

            mean_freq_unsorted = timetable.get_freq()
            mean_freq_sorted = sorted_timetable.get_freq()

            final_freq = (mean_freq_unsorted + mean_freq_sorted) / 2

            final_timetable = sorted_timetable.normalize_table_freq(final_freq)
            layer.create_line(line_name, stops, sections, final_timetable)

        else:
            pass


#################
### Script ###
#################

feed = Feed(gtfs_path)

feed_routes = feed.routes
feed_stops = feed.stops
feed_stop_times = feed.stop_times
feed_trips = feed.trips

# Tram = 0, Subway = 1, Bus = 3
list_tram_lines = extract_gtfs_stops(feed_routes, feed_stops, feed_stop_times, feed_trips, 0)
list_metro_lines = extract_gtfs_stops(feed_routes, feed_stops, feed_stop_times, feed_trips, 1)
list_bus_lines = extract_gtfs_stops(feed_routes, feed_stops, feed_stop_times, feed_trips, 3)

### Get the MLGraph without TCs
mnms_graph = load_graph(mnms_json_filepath)
roads = mnms_graph.roads

### Add the nodes, sections, and stops related to each PT line to the roadDescriptor
pt_lines = list_tram_lines + list_metro_lines + list_bus_lines
pt_lines_types = ['TRAM'] * len(list_tram_lines) + ['METRO'] * len(list_metro_lines) + ['BUS'] * len(list_bus_lines)
pt_nodes = {}

for line, line_type in zip(pt_lines, pt_lines_types):
    for ind, stop in line.iterrows():
        lat = float(stop["stop_lat_y"])
        lon = float(stop["stop_lon_y"])
        x_lam, y_lam = gps_to_lambert93(lat, lon)

        node_id = line_type + '_' + stop['route_short_name'] + '_' + cleanString(stop['stop_name_y'])
        pt_nodes[node_id] = [x_lam, y_lam]
        roads.register_node(node_id, [x_lam, y_lam])

        if ind > 0:
            onode_id = line_type + '_' + stop['route_short_name'] + '_' + cleanString(line.loc[ind-1, 'stop_name_y'])
            dnode_id = node_id
            section_id = line_type + '_' + stop['route_short_name'] + '_' + str(ind-1) + '_' + str(ind)
            section_length = _norm(np.array(pt_nodes[onode_id]) - np.array(pt_nodes[dnode_id]))
            roads.register_section(section_id, onode_id, dnode_id, section_length)
            roads.register_stop(onode_id, section_id, 0.)

        if ind == max(line.index):
            roads.register_stop(dnode_id, section_id, 1.)

### Overwrite the roads zoning with a new zoning including all sections
roads.add_zone(generate_one_zone("RES", roads))

### Create the PT layers, mob services and lines

# Tram
tram_service = PublicTransportMobilityService('TRAM')
tram_layer = PublicTransportLayer(roads, 'TRAMLayer', Tram, tram_default_speed,
        services=[tram_service])
generate_public_transportation_lines(feed_stop_times, tram_layer, list_tram_lines, 'TRAM_')

# Metro
metro_service = PublicTransportMobilityService('METRO')
metro_layer = PublicTransportLayer(roads, 'METROLayer', Metro, metro_default_speed,
        services=[metro_service])
generate_public_transportation_lines(feed_stop_times, metro_layer, list_metro_lines, 'METRO_')

# Bus
bus_service = PublicTransportMobilityService('BUS')
bus_layer = PublicTransportLayer(roads, 'BUSLayer', Bus, traditional_vehs_default_speed,
        services=[bus_service])
generate_public_transportation_lines(feed_stop_times, bus_layer, list_bus_lines, 'BUS_')

### Create the MLGraph with PT
mlgraph = MultiLayerGraph([tram_layer, metro_layer, bus_layer], None, None)

### Save the graph
save_graph(mlgraph, mlgraph_dump_file)