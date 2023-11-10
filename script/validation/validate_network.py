import os
import argparse
import json

import pandas as pd
import mpl_scatter_density
import numpy as np

from statistics import mean, median
from matplotlib import pyplot as plt
from matplotlib import colormaps


def validate_roads_tag(roads):
    valid = True

    nodes = roads.get("NODES")
    stops = roads.get("STOPS")
    sections = roads.get("SECTIONS")
    zones = roads.get("ZONES")

    if nodes is None:
        print(f"No tag NODES found in tag ROADS")
        valid = False

    if stops is None:
        print(f"No tag STOPS found in tag ROADS")
        valid = False

    if sections is None:
        print(f"No tag SECTIONS found in tag ROADS")
        valid = False

    if zones is None:
        print(f"No tag ZONES found in tag ROADS")
        valid = False

    return valid


def validate_layers_tag(layers):
    valid = True


def validate_roads(roads):
    roads_valid = True
    network_valid = validate_roads_tag(roads)

    print(f"Network (ROADS) valid : {network_valid}")

    return network_valid


def validate_layers(layers):
    layers_valid = True
    network_valid = validate_layers_tag(layers)

    print(f"Network (LAYERS) valid : {network_valid}")

    return network_valid


def build_adjacency_matrix(network):
    df_links = pd.DataFrame(network['ROADS']['SECTIONS'].values())

    all_nodes = np.union1d(df_links.upstream.unique(), df_links.downstream.unique())
    df_adj = pd.DataFrame(index=all_nodes, columns=all_nodes)

    for _, row in df_links.iterrows():
        df_adj.loc[row.upstream, row.downstream] = 1

    df_adj.fillna(0, inplace=True)

    return df_adj


def identify_deadends(df_adj):
    df_adj_de = df_adj.copy()
    s_deadEnds = (df_adj_de == 0).all(axis=1)
    ls_deadEnds = s_deadEnds[s_deadEnds].index
    while True:
        df_adj_de.loc[:, ls_deadEnds] = 0
        s_deadEnds = (df_adj_de == 0).all(axis=1)
        new_deadEnds = s_deadEnds[s_deadEnds].index
        if new_deadEnds.equals(ls_deadEnds):
            break
        else:
            ls_deadEnds = new_deadEnds
    ls_deadEnds = new_deadEnds

    return ls_deadEnds


def identify_springs(df_adj):
    df_adj_sp = df_adj.copy()
    s_springs = (df_adj_sp == 0).all(axis=0)
    ls_springs = s_springs[s_springs].index
    while True:
        df_adj_sp.loc[s_springs, :] = 0
        s_springs = (df_adj_sp == 0).all(axis=0)
        new_springs = s_springs[s_springs].index
        if new_springs.equals(ls_springs):
            break
        else:
            ls_springs = new_springs
    ls_springs = new_springs

    return ls_springs


def identify_final_sections(deadends):
    final_sections = []
    sections = roads.get("SECTIONS")

    for deadend in deadends:
        for id, section in sections.items():
            downnode = section["downstream"]
            if deadend == downnode:
                final_sections.append(section["id"])

    return final_sections


def compute_centralities(roads):
    nodes = roads.get("NODES")
    sections = roads.get("SECTIONS")
    centralities = {}

    for id, node in nodes.items():
        id_node = node["id"]
        for id, section in sections.items():
            upnode = section["upstream"]
            downnode = section["downstream"]
            if id_node == upnode:
                centralities[id_node] = centralities.get(id_node, 0) + 1
            if id_node == downnode:
                centralities[id_node] = centralities.get(id_node, 0) + 1

    return centralities


def analyze_roads(roads):
    nodes = roads.get("NODES")
    stops = roads.get("STOPS")
    sections = roads.get("SECTIONS")
    zones = roads.get("ZONES")

    sections_length = []

    for id, section in sections.items():
        sections_length.append(section["length"])

    print(f"Number of nodes : {len(nodes)}")
    print(f"Number of stops : {len(stops)}")
    print(f"Number of sections : {len(sections)}")
    print(f"Number of zones : {len(zones)}")
    print(f"Number of sections per zone : {len(sections) / len(zones)}")

    print(f"Min length of section : {min(sections_length)}")
    print(f"Max length of section : {max(sections_length)}")
    print(f"Mean length of section : {mean(sections_length)}")
    print(f"Median length of section : {median(sections_length)}")

    print(f"Connectivity index : {len(sections) / len(nodes)}")

    df_adj = build_adjacency_matrix(network)

    deadends = identify_deadends(df_adj)
    springs = identify_springs(df_adj)
    isolates = [value for value in deadends if value in springs]
    final_sections = identify_final_sections(list(deadends))

    print(f"Number of Dead-ends: {len(deadends)}")
    print(list(deadends))

    print(f"Number of Springs: {len(springs)}")
    print(list(springs))

    print(f"Number of Isolate nodes: {len(isolates)}")
    print(list(isolates))

    print((f"Number of Final sections: {len(final_sections)}"))
    print(final_sections)


def visualize_nodes(roads):
    nodes = roads.get("NODES")

    fig_nodes = plt.figure("Nodes", figsize=(20,12))
    fig_nodes.suptitle("Nodes")
    for id, node in nodes.items():
        x = float(node["position"][0])
        y = float(node["position"][1])
        plt.scatter(x, y, color="blue", s=1)


def visualize_stops(roads):
    stops = roads.get("STOPS")

    fig_stops = plt.figure("Stops", figsize=(20,12))
    fig_stops.suptitle("Stops")
    for id, stop in stops.items():
        x = float(stop["absolute_position"][0])
        y = float(stop["absolute_position"][1])
        plt.scatter(x, y, color="red", s=10)


def visualize_sections(roads):
    nodes = roads.get("NODES")
    sections = roads.get("SECTIONS")

    fig_sections = plt.figure("Sections", figsize=(20,12))
    fig_sections.suptitle("Sections")
    for id, section in sections.items():
        upnode = section["upstream"]
        downnode = section["downstream"]

        for id, node in nodes.items():
            if node["id"] == upnode:
                ux = float(node["position"][0])
                uy = float(node["position"][1])
            if node["id"] == downnode:
                dx = float(node["position"][0])
                dy = float(node["position"][1])

        plt.plot([ux, dx], [uy, dy])


def visualize_zones(roads):
    zones = roads.get("ZONES")
    fig_centralities = plt.figure("Zones", figsize=(20, 12))
    fig_centralities.suptitle("Zones")
    for id, res in zones.items():
        xvalues = []
        yvalues = []
        col = (np.random.random(), np.random.random(), np.random.random())
        contour = res["contour"]
        for point in contour:
            xvalues.append(float(point[0]))
            yvalues.append(float(point[1]))
        xvalues.append(xvalues[0])
        yvalues.append(yvalues[0])
        plt.plot(xvalues, yvalues, color=col)


def visualize_centralities(roads, centralities, max_degree):
    nodes = roads.get("NODES")
    xvalues = []
    yvalues = []
    dvalues = []

    for id, degree in centralities.items():
        node = nodes[id]
        xvalues.append(float(node["position"][0]))
        yvalues.append(float(node["position"][1]))
        dvalues.append(float(degree))

    fig_centralities = plt.figure("Centralities", figsize=(20,12))
    fig_centralities.suptitle("Centralities")
    plt.scatter(x=xvalues, y=yvalues, c=dvalues, cmap="YlOrRd", vmin=0, vmax=max_degree, s=1)


def visualize_pt_lines(roads, layers):
    nodes = roads.get("NODES")
    stops = roads.get("STOPS")

    for layer in layers:
        if layer["TYPE"] == "mnms.graph.layers.PublicTransportLayer":
            veh_type = layer["VEH_TYPE"]
            fig_layer = plt.figure(veh_type, figsize=(20, 12))
            fig_layer.suptitle(veh_type)
            lines = layer["LINES"]
            for line in lines:
                lstops = line["STOPS"]
                xvalues = []
                yvalues = []
                col = (np.random.random(), np.random.random(), np.random.random())
                for lstop in lstops:
                    stop = stops[lstop]
                    x = float(stop["absolute_position"][0])
                    xvalues.append(x)
                    y = float(stop["absolute_position"][1])
                    yvalues.append(y)
                    plt.scatter(x, y, color=col, s=10)
                plt.plot(xvalues, yvalues, color=col)


def extract_file(file):
    json_file = open(file)
    network = json.load(json_file)
    json_file.close()

    return network


def _path_file_type(path):
    if os.path.isfile(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid path")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate a JSON network file for MnMS")
    parser.add_argument('network_file', type=_path_file_type, help='Path to the network JSON file')
    parser.add_argument("--visualize", default=False, type=bool,
                        help="Visualize network, True or False")

    args = parser.parse_args()

    network = extract_file(args.network_file)

    roads = network.get("ROADS")
    layers = network.get("LAYERS")
    valid = True

    if roads is None:
        print(f"No tag ROADS found in JSON network file")
        valid = False
    else:
        valid = validate_roads(roads)

    if valid:
        analyze_roads(roads)

        centralities = compute_centralities(roads)
        print(f"Node with maximum centrality degree : {max(centralities, key=centralities.get)} = {max(centralities.values())}")

        if args.visualize:
            visualize_nodes(roads)
            visualize_stops(roads)
            visualize_sections(roads)
            visualize_centralities(roads, centralities, max(centralities.values()))
            visualize_zones(roads)
            visualize_pt_lines(roads, layers)
            plt.show()

