import os
import argparse
import pandas as pd
import csv


def analyze_users(df_users):
    print("analyze")


def extract_file(file):
    df_users = pd.read_csv(file, sep=';')

    return df_users


def _path_file_type(path):
    if os.path.isfile(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid path")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate a CSV user output file for MnMS")
    parser.add_argument("user_file", type=_path_file_type, help="Path to the user output csv file")

    args = parser.parse_args()

    df_users = extract_file(args.user_file)
    analyze_users(df_users)