import os
import argparse
import pandas as pd

from datetime import datetime


def validate_demand(file):
    df_users = pd.read_csv(file, sep=';')

    invalid_users_count = 0

    for index, user in df_users.iterrows():
        user_valid = True

        user_valid = validate_user_id(user)
        user_valid = validate_user_departure_time(user)
        user_valid = validate_user_origin(user)
        user_valid = validate_user_destination(user)
        user_valid = validate_user_journey(user)

        if not user_valid:
            print(f"User: {user} invalid")
            invalid_users_count = invalid_users_count + 1

    total_users = len(df_users)
    validation = 100 - invalid_users_count * 100 / total_users

    print(f"Total number of users: {len(df_users)}")
    print(f"Number of invalid users: {invalid_users_count}")
    print(f"Validation : {validation}%")


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
        if not isinstance(user_id, int):
            print(f"Invalid user id for user: {user[0]}")
            valid = False

        if not user_id > 0:
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
        user_origin = user[2]
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
        user_destination = user[3]
    else:
        print(f"No destination found for user: {user[0]}")
        valid = False

    return valid


def validate_user_journey(user):
    """Validate user journey

                    Parameters
                    ----------
                    user:

                    Returns
                    -------
                    valid: bool

                    """

    valid = True

    if user[2] == user[3]:
        print(f"Warning: origin equals destination for user {user[0]}, origin = destination = {user[2]}")

    return valid


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
    parser.add_argument('demand_file', type=_path_file_type, help='Path to the demand csv file')

    args = parser.parse_args()

    validate_demand(args.demand_file)