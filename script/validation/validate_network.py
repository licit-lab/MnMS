'''
Validation of a json MnMS file

WARNING: the notion of spring, dead-end and isolated node is incorrect if  the network is made up of several sub-graphs such as the metro (disjoint network)
'''
import os
import argparse
import json

import pandas as pd
import numpy as np

from statistics import mean, median
from matplotlib import pyplot as plt


def extract_file(file):
    json_file = open(file)
    network = json.load(json_file)
    json_file.close()

    return network


def validate_roads(roads):
    roads_valid = True
    network_valid = validate_roads_tag(roads)

    print(f"Network (ROADS) valid : {network_valid}")

    return network_valid


def analyze_network(roads):
    nodes = roads.get("NODES")
    stops = roads.get("STOPS")
    sections = roads.get("SECTIONS")
    zones = roads.get("ZONES")

    sections_length = []

    for id , node in nodes.items():
        node['upstream']= []
        node['downstream'] = []

    for id, section in sections.items():
        sections_length.append(section["length"])
        nodes[section['upstream']]['downstream'].append(id)
        nodes[section['downstream']]['upstream'].append(id)

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

    # Useless nodes
    n =0
    useless_nodes=[]
    for id, node in nodes.items():
        if len(node['upstream'])==1 and len(node['downstream'])==1:
            n=n+1
            useless_nodes.append(id)
    print(f"Number of useless nodes : {n}")
    print(useless_nodes)

def vizualize_nodes(roads):
    nodes = roads.get("NODES")

    for id, node in nodes.items():
        x = float(node["position"][0])
        y = float(node["position"][1])
        plt.scatter(x, y, color="blue", s=0.1)

    plt.show()


def vizualize_stops(roads):
    stops = roads.get("STOPS")

    for id, stop in stops.items():
        x = float(stop["absolute_position"][0])
        y = float(stop["absolute_position"][1])
        plt.scatter(x, y, color="red", s=0.1)

    plt.show()


def vizualize_sections(roads):
    stops = roads.get("SECTIONS")

    for id, stop in stops.items():
        x = float(stop["absolute_position"][0])
        y = float(stop["absolute_position"][1])
        plt.scatter(x, y, color="red", s=0.1)

    plt.show()


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

    # Search for upstream nodes that may be also considered as dead-end nodes (unless there are disjoint networks)
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

    # Search for downstream nodes that may be also considered as springs nodes (unless there are disjoint networks)
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
    valid = True

    if roads is None:
        print(f"No tag ROADS found in JSON network file")
        valid = False
    else:
        valid = validate_roads(roads)

    if valid:
        analyze_network(roads)

        df_adj = build_adjacency_matrix(network)

        deadends = identify_deadends(df_adj)
        print(f"Number of Dead-ends: {len(deadends)}")
        print(list(deadends))

        springs = identify_springs(df_adj)
        print(f"Number of Springs: {len(springs)}")
        print(list(springs))

        isolates = [value for value in deadends if value in springs]
        print(f"Number of Isolate nodes: {len(isolates)}")
        print(list(isolates))

        if args.visualize:
            vizualize_nodes(roads)
            vizualize_stops(roads)

