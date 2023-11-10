import os
import argparse
import json


def validate_transit_links():
    transit_links = "TODO"


def analyze_transit_links():
    transit_links = "TODO"


def visualize_transit_links():
    transit_links = "TODO"


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
    parser.add_argument("--visualize", default=False, type=bool,
                        help="Visualize transit links, True or False")

    args = parser.parse_args()

    transit_links = extract_file(args.transit_link_file)