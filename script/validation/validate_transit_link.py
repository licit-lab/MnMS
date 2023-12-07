import os
import argparse
import json

from statistics import mean, median
from matplotlib import pyplot as plt

def validate_transit_links():
    transit_links = "TODO"


def analyze_transit_links(tlinks):
    tl_length = []

    for tl in tlinks:
        tl_length.append(tl["LENGTH"])

    print(f"Number of transit links : {len(tl_length)}")
    print(f"Min length of transit link : {min(tl_length)}")
    print(f"Max length of transit link : {max(tl_length)}")
    print(f"Mean length of transit link : {mean(tl_length)}")
    print(f"Median length of transit link : {median(tl_length)}")


def visualize_transit_links(tlinks, roads, origins, destinations):
    nodes = roads.get("NODES")

    fig_nodes = plt.figure("Transit Links", figsize=(20, 12))
    fig_nodes.suptitle("Transit Links")

    for id, node in nodes.items():
        x = float(node["position"][0])
        y = float(node["position"][1])
        plt.scatter(x, y, color="grey", s=1)

    for tlink in tlinks:
        upnode = str(tlink["UPSTREAM"])
        downnode = str(tlink["DOWNSTREAM"])

        xu, yu, xd, yd = 0, 0, 0, 0

        if upnode.startswith("ORIGIN"):
            for id, origin in origins.items():
                if id == upnode:
                    xu = float(origin[0])
                    yu = float(origin[1])
        else:
            for id, node in nodes.items():
                if node["id"] == upnode:
                    xu = float(node["position"][0])
                    yu = float(node["position"][1])

        if downnode.startswith("DESTINATION"):
            for id, destination in destinations.items():
                if id == downnode:
                    xd = float(destination[0])
                    yd = float(destination[1])
        else:
            for id, node in nodes.items():
                if node["id"] == downnode:
                    xd = float(node["position"][0])
                    yd = float(node["position"][1])

        if xu != 0 and yu != 0 and xd != 0 and yd != 0:
            plt.plot([xu, xd], [yu, yd], color="red")


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
    parser = argparse.ArgumentParser(description="Validate a JSON transit_link file for MnMS")
    parser.add_argument('transit_link_file', type=_path_file_type, help='Path to the transit_link JSON file')
    parser.add_argument('network_file', type=_path_file_type, help='Path to the network JSON file')
    parser.add_argument('odlayer_file', type=_path_file_type, help='Path to the ODLayer JSON file')
    parser.add_argument("--visualize", default=False, type=bool, help="Visualize transit links, True or False")

    args = parser.parse_args()

    transit_links = extract_file(args.transit_link_file)
    tlinks = transit_links.get("LINKS")

    network = extract_file(args.network_file)
    roads = network.get("ROADS")

    odlayer = extract_file(args.odlayer_file)
    origins = odlayer.get("ORIGINS")
    destinations = odlayer.get("DESTINATIONS")

    analyze_transit_links(tlinks)

    if args.visualize:
        visualize_transit_links(tlinks, roads, origins, destinations)
        plt.show()