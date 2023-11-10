import os
import argparse
import math
import pandas as pd
import mpl_scatter_density

from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from datetime import datetime, timedelta


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
        print(f"No column named ID found in csv file")
        valid = False

    if "DEPARTURE" not in df_users.columns:
        print(f"No column named DEPARTURE found in csv file")
        valid = False

    if "ORIGIN" not in df_users.columns:
        print(f"No column named ORIGIN found in csv file")
        valid = False

    if "DESTINATION" not in df_users.columns:
        print(f"No column named DESTINATION found in csv file")
        valid = False

    if "MOBILITY SERVICES" not in df_users.columns:
        print(f"Warning: No column named MOBILITY SERVICES found in csv file")

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

    if user["ID"]:
        user_id = user["ID"]
        if not (isinstance(user_id, int) or isinstance(user_id, str)):
            print(f"Invalid user id for user: {user_id}")
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
    user_id = user["ID"]

    if user["DEPARTURE"]:
        departure_time = user["DEPARTURE"]
        try:
            datetime.strptime(departure_time, time_format)
        except ValueError:
            print(f"Invalid departure time for user: {user_id}")
            valid = False
    else:
        print(f"No departure time found for user: {user_id}")
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
    user_id = user["ID"]

    if user["ORIGIN"]:
        user_origin = user["ORIGIN"].split(' ')

        if user_origin[0]:
            if not isinstance(float(user_origin[0]), float):
                print(f"Invalid user origin x coordinate for user: {user_id}")
                valid = False
        else:
            print(f"No origin x coordinate found for user: {user_id}")
            valid = False

        if user_origin[1]:
            if not isinstance(float(user_origin[1]), float):
                print(f"Invalid user origin y coordinate for user: {user_id}")
                valid = False
        else:
            print(f"No origin y coordinate found for user: {user_id}")
            valid = False

    else:
        print(f"No origin found for user: {user_id}")
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
    user_id = user["ID"]

    if user["DESTINATION"]:
        user_destination = user["DESTINATION"].split(' ')

        if user_destination[0]:
            if not isinstance(float(user_destination[0]), float):
                print(f"Invalid user destination x coordinate for user: {user_id}")
                valid = False
        else:
            print(f"No destination x coordinate found for user: {user_id}")
            valid = False

        if user_destination[1]:
            if not isinstance(float(user_destination[1]), float):
                print(f"Invalid user destination y coordinate for user: {user_id}")
                valid = False
        else:
            print(f"No destination y coordinate found for user: {user_id}")
            valid = False

    else:
        print(f"No destination found for user: {user_id}")
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

    user_id = user["ID"]
    origin = user["ORIGIN"].split(' ')
    destination = user["DESTINATION"].split(' ')
    distance = math.dist([float(origin[0]), float(origin[1])], [float(destination[0]), float(destination[1])])

    if user["ORIGIN"] == user["DESTINATION"]:
        print(f"Warning: origin equals destination for user {user_id}, origin = destination = {user['ORIGIN']}")
        warning = True

    elif distance < radius:
        print(f"Warning: origin/destination distance lesser than radius {radius}, for user {user_id}, distance = {distance}")
        warning = True

    return valid, warning


def check_user_ms_defined(user):

    ms_defined = False

    if user["MOBILITY SERVICES"]:
        ms_defined = True

    return ms_defined


def check_user_id_duplicates(df_users):
    """Validate user id

                    Parameters
                    ----------
                    users: Dataframe

                    Returns
                    -------
                    valid: bool

                    """

    valid = True

    ids = df_users["ID"]
    id_duplicates = df_users[ids.isin(ids[ids.duplicated()])].sort_values("ID")
    count_duplicates = 0

    if not id_duplicates.empty:
        print(f"Id duplicates : {id_duplicates['ID']}")

        count_duplicates = len(df_users["ID"]) - len(df_users["ID"].drop_duplicates())
        print(f"Number of duplicates : {count_duplicates}")
        valid = False

    return valid


def count_ms_occurences(df_users):
    ms_occurences = {}

    users_ms = df_users["MOBILITY SERVICES"]

    for user_ms in users_ms:
        mobility_services = user_ms.split(' ')
        for mobility_service in mobility_services:
            ms_occurences[mobility_service] = ms_occurences.get(mobility_service, 0) + 1

    return ms_occurences


def scatter_density(fig, x, y, title):
    # "Viridis-like" colormap with white background
    white_viridis = LinearSegmentedColormap.from_list('white_viridis', [
        (0, '#ffffff'),
        (1e-20, '#440053'),
        (0.2, '#404388'),
        (0.4, '#2a788e'),
        (0.6, '#21a784'),
        (0.8, '#78d151'),
        (1, '#fde624'),
    ], N=256)

    ax = fig.add_subplot(1, 1, 1, projection="scatter_density")
    ax.set_title(title)
    density = ax.scatter_density(x, y, dpi=18, vmin=0, vmax=50, cmap=white_viridis)
    fig.colorbar(density, label="Number of points per pixel")


def validate_demand(df_users, radius):
    invalid_users_count = 0
    warning_users_count = 0

    check_user_id_duplicates(df_users)

    for index, user in df_users.iterrows():
        user_valid = True
        user_warning = False

        user_valid = validate_user_id(user)
        if user_valid:
            user_valid = validate_user_departure_time(user)
            if user_valid:
                user_valid = validate_user_origin(user)
                if user_valid:
                    user_valid = validate_user_destination(user)
                    if user_valid:
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
    print(f"First user departure time: {df_users['DEPARTURE'].min()}")
    print(f"Last user departure time: {df_users['DEPARTURE'].max()}")

    user_ms_defined_count = 0
    ms_occurences = {}

    if "MOBILITY SERVICES" in df_users.columns:
        for index, user in df_users.iterrows():
            user_ms_defined = check_user_ms_defined(user)
            if user_ms_defined:
                user_ms_defined_count = user_ms_defined_count + 1

        ms_occurences = count_ms_occurences(df_users)

    print(f"Number of users with at least one mandatory mobility service : {user_ms_defined_count}")
    print(f"Mandatory mobility services and occurences: {ms_occurences}")


def visualize_demand(df_users):
    # Origins
    ox = []
    oy = []

    for index, user in df_users.iterrows():
        origin = user["ORIGIN"].split(' ')
        ox.append(float(origin[0]))
        oy.append(float(origin[1]))

    fig1 = plt.figure(figsize=(20,12))
    scatter_density(fig1, ox, oy, "Origin coordinates density")

    # Destinations
    dx = []
    dy = []

    for index, user in df_users.iterrows():
        destination = user["DESTINATION"].split(' ')
        dx.append(float(destination[0]))
        dy.append(float(destination[1]))

    fig2 = plt.figure(figsize=(20,12))
    scatter_density(fig2, dx, dy, "Destination coordinates density")

    # Dynamic
    dnx = []
    dny = []

    time_format = "%H:%M:%S"
    df_users["DEPARTURE"] = pd.to_datetime(df_users["DEPARTURE"], format=time_format)
    df_users = df_users.set_index(pd.DatetimeIndex(df_users["DEPARTURE"]))

    start_time = df_users["DEPARTURE"].min()
    end_time = df_users["DEPARTURE"].max()

    time_cur = start_time
    while time_cur < end_time:
        time_inc = time_cur + timedelta(minutes=0, seconds=59)
        user_range = df_users.between_time(time_cur.time(), time_inc.time())
        dnx.append(time_cur)
        dny.append(len(user_range))
        time_cur = time_inc + timedelta(seconds=1)

    fig3 = plt.figure(figsize=(20,12))
    fig3.suptitle("Demand dynamic")
    plt.plot(dnx, dny)

    plt.show()


def extract_file(file):
    df_users = pd.read_csv(file, sep=';')

    return df_users


def _path_file_type(path):
    if os.path.isfile(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid path")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate a CSV demand file for MnMS")
    parser.add_argument("demand_file", type=_path_file_type, help="Path to the demand csv file")
    parser.add_argument("--radius", default=0, type=float, help="Tolerance radius in meters")
    parser.add_argument("--visualize", default=False, type=bool,
                        help="Visualize demand origin/destination, True or False")

    args = parser.parse_args()

    df_users = extract_file(args.demand_file)
    validate_demand(df_users, args.radius)
    analyze_demand(df_users)

    if args.visualize:
        visualize_demand(df_users)