import os
import argparse
import pandas as pd
import numpy as np


def analyze_paths(df_paths):
    print(f"First user departure time: {df_paths['TIME'].min()}")
    print(f"Last path departure time: {df_paths['TIME'].max()}")

    total_paths = len(df_paths)
    paths_inf_cost = 0
    paths_not_defined = 0
    paths_inf_length = 0
    paths_services_not_defined = 0
    paths_path_not_chosen = 0

    for index, path in df_paths.iterrows():
        if path["COST"] == np.inf:
            paths_inf_cost = paths_inf_cost + 1
        if path["PATH"] == '':
            paths_not_defined = paths_not_defined + 1
        if path["LENGTH"] == np.inf:
            paths_inf_length = paths_inf_length + 1
        if path["SERVICES"] == '':
            paths_services_not_defined = paths_services_not_defined + 1
        if path["CHOSEN"] == '':
            paths_path_not_chosen = paths_path_not_chosen + 1

    print(f"Total number of paths: {total_paths}")
    print(f"Number of users with a infinite path cost: {paths_inf_cost}")
    print(f"Number of users without path defined: {paths_not_defined}")
    print(f"Number of users with a infinite path length: {paths_inf_length}")
    print(f"Number of users without mobility services defined: {paths_services_not_defined}")
    print(f"Number of users without path chosen: {paths_path_not_chosen}")


def extract_file(file):
    df = pd.read_csv(file, sep=';', keep_default_na=False)

    return df


def _path_file_type(path):
    if os.path.isfile(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid path")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate a CSV path output file for MnMS")
    parser.add_argument("path_file", type=_path_file_type, help="Path to the path output csv file")

    args = parser.parse_args()

    df_paths = extract_file(args.path_file)
    analyze_paths(df_paths)
