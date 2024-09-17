import os
import argparse
import pandas as pd
import csv


def analyze_paths(df_paths):
    print("analyze")


def extract_file(file):
    df_paths = pd.read_csv(file, sep=';')

    return df_paths


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
