import os
import argparse
import math

import pandas as pd
from matplotlib import pyplot as plt

from datetime import datetime

def extract_file(file):
    df_users = pd.read_csv(file, sep=';')

    return df_users


def validate_demand(df_users, radius):
    invalid_users_count = 0
    warning_users_count = 0

    for index, user in df_users.iterrows():
        user_valid = True
        user_warning = False

        user_valid = validate_user_id(user)
        user_valid = validate_user_departure_time(user)
        user_valid = validate_user_origin(user)
        user_valid = validate_user_destination(user)
        user_valid, user_warning = validate_user_journey(user, radius)

        if not user_valid:
            print(f"User: {user} invalid")
            invalid_users_count = invalid_users_count + 1

        if user_warning:
            warning_users_count = warning_users_count + 1

    total_users = len(df_users)
    validation = 100 - invalid_users_count * 100 / total_users

    print(f"Total number of users: {len(df_users)}")
    print(f"Number of invalid users: {invalid_users_count}")
    print(f"Number of warning users: {warning_users_count}")
    print(f"Validation : {validation}%")


def analyze_demand(df_users):

    user_ms_defined_count = 0
    for index, user in df_users.iterrows():
        user_ms_defined = check_user_ms_defined(user)

        if user_ms_defined:
            user_ms_defined_count = user_ms_defined_count + 1

    print(f"Number of users with at least one mandatory mobility service : {user_ms_defined_count}")


def visualize_demand(df_users):

    # Origins

    for index, user in df_users.iterrows():
        origin = user[2].split(' ')
        plt.scatter(float(origin[0]), float(origin[1]), color="blue", s=0.1)

    # Destinations

    for index, user in df_users.iterrows():
        destination = user[3].split(' ')
        plt.scatter(float(destination[0]), float(destination[1]), color="green", s=0.1)

    plt.show()



def validate_demand_columns(df_users):
    """Validate demand csv columns

                    Parameters
                    ----------
                    df_user: DataFrame

                    Returns
                    -------
                    valid: bool

                    """

    valid = True

    if "ID" not in df_users.columns:
        print(f"No column ID found in csv file")
        valid = False

    if "DEPARTURE" not in df_users.columns:
        print(f"No column DEPARTURE found in csv file")
        valid = False

    if "ORIGIN" not in df_users.columns:
        print(f"No column ORIGIN found in csv file")
        valid = False

    if "DESTINATION" not in df_users.columns:
        print(f"No column DESTINATION found in csv file")
        valid = False

    if "SERVICE" not in df_users.columns:
        print(f"Warning: No column SERVICE found in csv file")

    return valid


def validate_user_id(user):
    """Validate user id

                Parameters
                ----------
                user:

                Returns
                -------
                valid: bool

                """

    valid = True

    if user[0]:
        user_id = user[0]
        if not isinstance(user_id, str):
            print(f"Invalid user id for user: {user[0]}")
            valid = False
            
    else:
        print(f"No id found for user: {user}")
        valid = False

    return valid


def validate_user_departure_time(user):
    """Validate departure time

                    Parameters
                    ----------
                    user:

                    Returns
                    -------
                    valid: bool

                    """

    valid = True
    time_format = "%H:%M:%S"

    if user[1]:
        departure_time = user[1]
        try:
            datetime.strptime(departure_time, time_format)
        except ValueError:
            print(f"Invalid departure time for user: {user[0]}")
            valid = False
    else:
        print(f"No departure time found for user: {user[0]}")
        valid = False

    return valid


def validate_user_origin(user):
    """Validate user origin

                    Parameters
                    ----------
                    user:

                    Returns
                    -------
                    valid: bool

                    """

    valid = True

    if user[2]:
        user_origin = user[2].split(' ')

        if user_origin[0]:
            if not isinstance(float(user_origin[0]), float):
                print(f"Invalid user origin x coordinate for user: {user[0]}")
                valid = False
        else:
            print(f"No origin x coordinate found for user: {user[0]}")
            valid = False

        if user_origin[1]:
            if not isinstance(float(user_origin[1]), float):
                print(f"Invalid user origin y coordinate for user: {user[0]}")
                valid = False
        else:
            print(f"No origin y coordinate found for user: {user[0]}")
            valid = False

    else:
        print(f"No origin found for user: {user[0]}")
        valid = False

    return valid


def validate_user_destination(user):
    """Validate user destination

                    Parameters
                    ----------
                    user:

                    Returns
                    -------
                    valid: bool

                    """

    valid = True

    if user[3]:
        user_destination = user[3].split(' ')

        if user_destination[0]:
            if not isinstance(float(user_destination[0]), float):
                print(f"Invalid user destination x coordinate for user: {user[0]}")
                valid = False
        else:
            print(f"No destination x coordinate found for user: {user[0]}")
            valid = False

        if user_destination[1]:
            if not isinstance(float(user_destination[1]), float):
                print(f"Invalid user destination y coordinate for user: {user[0]}")
                valid = False
        else:
            print(f"No destination y coordinate found for user: {user[0]}")
            valid = False

    else:
        print(f"No destination found for user: {user[0]}")
        valid = False

    return valid


def validate_user_journey(user, radius):
    """Validate user journey

                    Parameters
                    ----------
                    user:

                    Returns
                    -------
                    valid: bool

                    """

    valid = True
    warning = False

    origin = user[2].split(' ')
    destination = user[3].split(' ')
    distance = math.dist([float(origin[0]), float(origin[1])], [float(destination[0]), float(destination[1])])

    if user[2] == user[3]:
        print(f"Warning: origin equals destination for user {user[0]}, origin = destination = {user[2]}")
        warning = True

    elif distance < radius:
        print(f"Warning: origin/destination distance lesser than radius {radius}, for user {user[0]}, distance = {distance}")
        warning = True

    return valid, warning

def check_user_ms_defined(user):

    ms_defined = False

    if user[4]:
        ms_defined = True

    return ms_defined

def check_user_id_duplicates(users):
    """Validate user id

                    Parameters
                    ----------
                    users: Dataframe

                    Returns
                    -------
                    valid: bool

                    """

    valid = True

    return valid


def _path_file_type(path):
    if os.path.isfile(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid path")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate a CSV demand file for MnMS")
    parser.add_argument("demand_file", type=_path_file_type, help="Path to the demand csv file")
    parser.add_argument("--radius", default=0, type=float, help="Tolerance radius in meters")
    parser.add_argument("--visualize", default=False, type=bool, help="Visualize demand origin/destination, True or False")

    args = parser.parse_args()

    df_users = extract_file(args.demand_file)
    validate_demand(df_users, args.radius)
    analyze_demand(df_users)

    if args.visualize:
        visualize_demand(df_users)