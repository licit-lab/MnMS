### WORK IN PROGRESS ###

###############
### Imports ###
###############
import networkx.exception
import numpy as np
import math
import networkx as nx

from gtfs_functions import Feed
from unidecode import unidecode
from coordinates import gps_to_lambert93, gps_to_utm
from mnms.graph.layers import PublicTransportLayer, MultiLayerGraph
from mnms.vehicles.veh_type import Tram, Metro, Bus, Funicular
from mnms.generation.zones import generate_one_zone
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import TimeTable, Time
from mnms.io.graph import load_graph, save_graph


##################
### Parameters ###
##################

gtfs_path = "lyon_tcl.zip" # gtfs zip folder
mnms_json_filepath = "lyon_roads.json" # mlgraph with the road network only

mlgraph_dump_file = "lyon_mnms_gtfs_bus_tram_metro.json"

# Default speeds
traditional_vehs_default_speed = 13.8 # m/s
metro_default_speed = 15 # m/s
tram_default_speed = 18 # m/s
funicular_default_speed = 5 # m/s

# Map match max distance
mapmatch_dist = 50

#################
### Functions ###
#################

_norm = np.linalg.norm

# choose here your final coordinates system (ex: Lyon/Symuvia = Lambert 93, International/Other = UTM)
_convert_coords = gps_to_lambert93

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
            line_name = line.iloc[0]['route_short_name']
            line_id = prefix_line_name + line_name

            stops = [line_id + '_' + cleanString(stp) for stp in list(line["stop_name_y"])]
            sections = [[line_id + f'_{ind}_{ind+1}', line_id + f'_{ind+1}_{ind+2}'] for ind in list(line.index)[:-2]] + [[line_id + f'_{line.index[-2]}_{line.index[-1]}']]

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
            layer.create_line(line_id, stops, sections, final_timetable)

        else:
            pass


def generate_map_matching_pt_lines(stop_times_, layer, list_lines, map_match_sections, prefix_line_name):
    """Function that generates a map matching public transportation lines on a layer with a certain frequency.

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
            line_name = line.iloc[0]['route_short_name']
            line_id = prefix_line_name + line_name

            stops = [line_id + '_' + cleanString(stp) for stp in list(line["stop_name_y"])]

            sections = map_match_sections[line_id]

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
            layer.create_line(line_id, stops, sections, final_timetable)

        else:
            pass


def register_pt_lines(pt_lines, pt_lines_types):

    pt_nodes = {}

    for line, line_type in zip(pt_lines, pt_lines_types):
        for ind, stop in line.iterrows():
            lat = float(stop["stop_lat_y"])
            lon = float(stop["stop_lon_y"])

            x_coord, y_coord = _convert_coords(lat, lon)

            node_id = line_type + '_' + stop['route_short_name'] + '_' + cleanString(stop['stop_name_y'])
            pt_nodes[node_id] = [x_coord, y_coord]
            roads.register_node(node_id, [x_coord, y_coord])

            dnode_id = node_id
            section_id = ""

            if ind > 0:
                onode_id = line_type + '_' + stop['route_short_name'] + '_' + cleanString(
                    line.loc[ind - 1, 'stop_name_y'])

                section_id = line_type + '_' + stop['route_short_name'] + '_' + str(ind - 1) + '_' + str(ind)
                section_length = _norm(np.array(pt_nodes[onode_id]) - np.array(pt_nodes[dnode_id]))
                roads.register_section(section_id, onode_id, dnode_id, section_length)
                roads.register_stop(onode_id, section_id, 0.)

            if ind == max(line.index):
                roads.register_stop(dnode_id, section_id, 1.)


def closest_node(graph, x, y):
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

    for id, node in graph.nodes(data=True):
        # Skip nodes without 'position' attribute
        if "position" not in node:
            continue

        # Extract the position of the current node
        node_x, node_y = node["position"]

        # Calculate the Euclidean distance
        distance = math.sqrt((node_x - x) ** 2 + (node_y - y) ** 2)

        # Update the closest node if a smaller distance is found
        if distance < min_distance:
            closest_node = id
            min_distance = distance

    return closest_node, min_distance

def generate_nx_graph(nodes, sections):

    # Create a directed graph
    nxgraph = nx.MultiDiGraph()

    # Add nodes to the graph
    for id, node in nodes.items():
        node_id = node.id
        x = float(node.position[0])
        y = float(node.position[1])
        nxgraph.add_node(node_id, position=(x, y))

    # Add edges to the graph
    for id, section in sections.items():
        edge_id = section.id
        upnode = section.upstream
        downnode = section.downstream
        length = section.length
        nxgraph.add_edge(upnode, downnode, id=edge_id, length=length)

    return nxgraph


def register_map_match_pt_lines(pt_lines, pt_lines_types, prefix_line_name):

    #roads_nodes = roads.nodes
    roads_nodes = mnms_graph.graph.nodes
    roads_sections = roads.sections

    # nx graph
    nxgraph = generate_nx_graph(roads_nodes, roads_sections)

    # empty lines map matching sections list dict (key: line_id, value: list of list of sections between 2 stops)
    lines_mm_sections_dict = {}

    pt_nodes = {}

    for line, line_type in zip(pt_lines, pt_lines_types):

        line_name = ""

        try:
            line_name = line.iloc[0]['route_short_name']
        except IndexError:
            print(f"No line name found for line : {line}")

        if line_name == "":
            continue
        else:
            line_id = prefix_line_name + line_name
            sections_paths_list = []

            for ind, stop in line.iterrows():
                lat = float(stop["stop_lat_y"])
                lon = float(stop["stop_lon_y"])

                x_coord, y_coord = _convert_coords(lat, lon)

                node_id = line_type + '_' + stop['route_short_name'] + '_' + cleanString(stop['stop_name_y'])
                pt_nodes[node_id] = [x_coord, y_coord]
                roads.register_node(node_id, [x_coord, y_coord])

                dnode_id = node_id
                section_id = ""
                shortest_path = []
                n = 0 # length of shortest_path

                sections_path = []

                if ind > 0:
                    onode_id = line_type + '_' + stop['route_short_name'] + '_' + cleanString(line.loc[ind - 1, 'stop_name_y'])
                    o_lat = float(line.loc[ind - 1, 'stop_lat_y'])
                    o_lon = float(line.loc[ind - 1, 'stop_lon_y'])
                    o_x_coord, o_y_coord = _convert_coords(o_lat, o_lon)

                    # find closest road node to origin stop
                    id_closest_origin_node, dist_o = closest_node(nxgraph, o_x_coord, o_y_coord)

                    # find closest road node to destination stop
                    id_closest_destination_node, dist_d = closest_node(nxgraph, x_coord, y_coord)

                    # radius 50 meters for closest node to stop
                    if dist_o < mapmatch_dist and dist_d < mapmatch_dist:
                        try:
                            shortest_path = nx.shortest_path(nxgraph,
                                                             source=id_closest_origin_node,
                                                             target=id_closest_destination_node,
                                                             weight="length")
                        except networkx.exception.NetworkXNoPath:
                            shortest_path = []

                        # shortest_path_edges = list(zip(shortest_path[:-1], shortest_path[1:]))
                        n = len(shortest_path)

                        # empty shortest path (at least two)
                        if n < 2:
                            first_node = onode_id
                            second_node = node_id
                        else:
                            first_node = shortest_path[0]
                            second_node = shortest_path[1]
                    else:
                        n = 0
                        first_node = onode_id
                        second_node = node_id

                    # section to find
                    for id, road_section in roads_sections.items():
                        if road_section.upstream == first_node and road_section.downstream == second_node:
                            section_id = road_section.id
                    # if section not found
                    if section_id == "":
                        # print(f"Section not found for origin node : {onode_id}")
                        section_id = line_type + '_' + stop['route_short_name'] + '_' + str(ind - 1) + '_' + str(ind)
                        section_length = _norm(np.array(pt_nodes[onode_id]) - np.array(pt_nodes[dnode_id]))
                        roads.register_section(section_id, onode_id, dnode_id, section_length)

                    roads.register_stop(onode_id, section_id, 0.)

                    section_path_id = ""

                    if n < 2:
                        sections_path.append(section_id)

                    else:
                        # build sections path
                        for i in range(n):

                            if i > 0:
                                for id, road_section in roads_sections.items():
                                    if road_section.upstream == shortest_path[i-1] and road_section.downstream == shortest_path[i]:
                                        section_path_id = road_section.id
                                        sections_path.append(section_path_id)
                                if section_path_id == "":
                                    print(f"Section not found for nodes : {shortest_path[i-1]} and {shortest_path[i]}")

                            # May not be necessary
                            # if i == n-1:
                                # sections_path.append(section_path_id)

                    sections_paths_list.append(sections_path)

                if ind == max(line.index):
                    # if section not found
                    if section_id == "":
                        print(f"Section not found for destination node : {dnode_id}")
                    else:
                        roads.register_stop(dnode_id, section_id, 1.)

            # connect sections_pathss
            for i, sections_path in enumerate(sections_paths_list):
                # for each sections_paths without last one
                if i < len(sections_paths_list) - 1:
                    # add the first section of the next sections_path
                    sections_path.append(sections_paths_list[i+1][0])

            lines_mm_sections_dict[line_id] = sections_paths_list

    return lines_mm_sections_dict


#################
### Script ###
#################

feed = Feed(gtfs_path)

feed_routes = feed.routes
feed_stops = feed.stops
feed_stop_times = feed.stop_times
feed_trips = feed.trips

# Tram = 0, Subway = 1, Bus = 3, Funicular = 7
list_tram_lines = extract_gtfs_stops(feed_routes, feed_stops, feed_stop_times, feed_trips, 0)
list_metro_lines = extract_gtfs_stops(feed_routes, feed_stops, feed_stop_times, feed_trips, 1)
list_bus_lines = extract_gtfs_stops(feed_routes, feed_stops, feed_stop_times, feed_trips, 3)
#list_funicular_lines = extract_gtfs_stops(feed_routes, feed_stops, feed_stop_times, feed_trips, 7)

### Get the MLGraph without TCs
mnms_graph = load_graph(mnms_json_filepath)
roads = mnms_graph.roads


### Add the nodes, sections, and stops related to each PT line to the roadDescriptor
pt_lines = list_tram_lines + list_metro_lines + list_bus_lines
pt_lines_types = ['TRAM'] * len(list_tram_lines) + ['METRO'] * len(list_metro_lines)

register_pt_lines(pt_lines, pt_lines_types)


### Add the nodes ands stops related to each map matched PT line to the roadDescriptor
map_match_bus_line_type = ['BUS'] * len(list_bus_lines)

bus_lines_map_match_sections = register_map_match_pt_lines(list_bus_lines, map_match_bus_line_type, 'BUS_')


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
# generate_public_transportation_lines(feed_stop_times, bus_layer, list_bus_lines, 'BUS_')
generate_map_matching_pt_lines(feed_stop_times, bus_layer, list_bus_lines, bus_lines_map_match_sections, 'BUS_')

# Funicular
# funicular_service = PublicTransportMobilityService('FUNI')
# funicular_layer = PublicTransportLayer(roads, 'FUNIlayer', Funicular, funicular_default_speed, services=[funicular_service])
# generate_public_transportation_lines(feed_stop_times, funicular_layer, list_funicular_lines, 'FUNI_')


### Create the MLGraph with PT
mlgraph = MultiLayerGraph([tram_layer, metro_layer, bus_layer], None, None)


### Save the graph
save_graph(mlgraph, mlgraph_dump_file)