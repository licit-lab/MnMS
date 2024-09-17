import os
import argparse
import pandas as pd


def analyze_users(df_users):
    print(f"First user activity time: {df_users['TIME'].min()}")
    print(f"Last user activity time: {df_users['TIME'].max()}")

    users_without_link = 0
    users_without_position = 0
    users_deadend = 0

    users_arrived = 0

    for index, user in df_users.iterrows():
        if user["LINK"] == '':
            users_without_link = users_without_link + 1
        if user["POSITION"] == '':
            users_without_position = users_without_position + 1
        if user["STATE"] == "DEADEND":
            users_deadend = users_deadend + 1
        if user["STATE"] == "ARRIVED":
            users_arrived = users_arrived + 1

    print(f"Number of users without link: {users_without_link}")
    print(f"Number of users without position: {users_without_position}")
    print(f"Number of users in deadend state: {users_deadend}")

    print(f"Number of users arrived to destination: {users_arrived}")



def extract_file(file):
    df = pd.read_csv(file, sep=';', keep_default_na=False)

    return df


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