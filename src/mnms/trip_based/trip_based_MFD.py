import numpy as np
import copy

# Define the region in which the vehicles of the same kind have the same mean speed, depending on the current
# accumulation of vehicles
class Reservoir(object):
    # id to identify the sensor, is not used for now, could be a string
    # modes are the transportation modes available for the sensor
    # fct_MFD_speed is the function returning the mean speeds as a function of the accumulations
    def __init__(self, id: int, modes, fct_MFD_speed):
        self.id = id
        self.modes = modes
        self.compute_MFD_speed = fct_MFD_speed
        dict_accumulations = {}
        for mode in modes:
            dict_accumulations[mode] = 0
        self.dict_accumulations = dict_accumulations
        self.dict_speeds = {}
        self.update_speeds()
        return

    def update_accumulations(self, dict_accumulations):
        for mode in dict_accumulations.keys():
            if mode in self.modes:
                self.dict_accumulations[mode] = dict_accumulations[mode]
        return

    def update_speeds(self):
        self.dict_speeds = self.compute_MFD_speed(self.dict_accumulations)
        return self.dict_speeds


def calculate_trip_times(departure_times, trip_legs, time_stop=3600, delta_t=20, accumulation_weights=None,
                         list_reservoirs=[]):
    # INPUTS
    # departure_times: list of departure times of all agents
    # trip_legs: list of the trip legs (mode, sensor, distance) of all agents
    # time_stop: duration of the simulation
    # delta_t=20: time step for the numerical resolution
    # accumulation_weights: list of number of travelers of all agents. If None, it assumes each agent is one traveler
    # list_reservoirs: list of the Reservoir objects to describe the transportation network
    # OUTPUTS
    # list_time_completion_legs: list of the travel time per leg of all agents. -1 means the leg has not been completed
    # during the simulation
    nb_users = len(departure_times)
    nb_steps = time_stop // delta_t
    if not accumulation_weights:  # default is every trip is a car user
        accumulation_weights = np.ones(nb_users)

    list_dict_accumulations = []
    list_dict_speeds = []
    for res in list_reservoirs:
        list_dict_accumulations.append(res.dict_accumulations)
        list_dict_speeds.append(res.dict_speeds)
    hist_accumulations = []
    hist_speeds = []

    list_current_leg = np.zeros(nb_users, dtype='int')
    list_remaining_length = np.zeros(nb_users)
    list_current_mode = [0] * nb_users
    list_current_reservoir = np.zeros(nb_users, dtype='int')
    list_time_completion_legs = []
    for i_user in range(nb_users):
        list_remaining_length[i_user] = trip_legs[i_user][list_current_leg[i_user]]['length']
        list_current_mode[i_user] = trip_legs[i_user][list_current_leg[i_user]]['mode']
        list_current_reservoir[i_user] = trip_legs[i_user][list_current_leg[i_user]]['sensor']
        list_time_completion_legs.append([-1] * len(trip_legs[i_user]))
    started_trips = [False] * nb_users
    completed_trips = [False] * nb_users
    time = 0
    for i_step in range(nb_steps):
        time += delta_t
        # Update the traffic conditions
        for i_res, res in enumerate(list_reservoirs):
            res.update_accumulations(list_dict_accumulations[i_res])
            list_dict_speeds[i_res] = res.update_speeds()
        hist_accumulations.append(copy.deepcopy(list_dict_accumulations))
        hist_speeds.append(list_dict_speeds.copy())
        # Move the agents
        for i_user in range(nb_users):
            # Agent enters the network
            if (not started_trips[i_user]) and (departure_times[i_user] <= time):
                print(i_user, time, departure_times[i_user])
                started_trips[i_user] = True
                print("CURR RES:", list_current_reservoir[i_user])
                print("CURR MODE:", list_current_mode[i_user])
                print("ACC:", list_dict_accumulations)
                list_dict_accumulations[list_current_reservoir[i_user]][list_current_mode[i_user]] += \
                    accumulation_weights[i_user]
            # Agent is on the network
            if (not completed_trips[i_user]) and (started_trips[i_user]):
                remaining_time = delta_t
                # print(list_remaining_length[i_user] <= remaining_time*list_dict_speeds[list_current_reservoir[i_user]][list_current_mode[i_user]],list_current_leg[i_user] < len(trip_legs[i_user])-1)
                # Complete current trip leg
                print("DICT SPEEDS", list_dict_speeds)
                while list_remaining_length[i_user] <= remaining_time * \
                        list_dict_speeds[list_current_reservoir[i_user]][list_current_mode[i_user]] and \
                        list_current_leg[i_user] < len(trip_legs[i_user]) - 1:
                    remaining_time -= list_remaining_length[i_user] / list_dict_speeds[list_current_reservoir[i_user]][
                        list_current_mode[i_user]]
                    list_dict_accumulations[list_current_reservoir[i_user]][list_current_mode[i_user]] -= \
                        accumulation_weights[i_user]
                    list_time_completion_legs[i_user][list_current_leg[i_user]] = time
                    list_current_leg[i_user] += 1
                    print('leg', i_user, list_current_leg[i_user])
                    list_remaining_length[i_user] = trip_legs[i_user][list_current_leg[i_user]]['length']
                    list_current_mode[i_user] = trip_legs[i_user][list_current_leg[i_user]]['mode']
                    list_current_reservoir[i_user] = trip_legs[i_user][list_current_leg[i_user]]['sensor']
                    list_dict_accumulations[list_current_reservoir[i_user]][list_current_mode[i_user]] += \
                        accumulation_weights[i_user]
                # Remove accomplished distance
                list_remaining_length[i_user] -= remaining_time * list_dict_speeds[list_current_reservoir[i_user]][
                    list_current_mode[i_user]]
                # print(i_user, remaining_time*list_dict_speeds[list_current_reservoir[i_user]][list_current_mode[i_user]])
                # print(i_step, i_user, remaining_time*list_dict_speeds[list_current_reservoir[i_user]][list_current_mode[i_user]])
                # Remove agent who reached destinations
                if list_remaining_length[i_user] <= 0:
                    # Improvement pt: could take the ratio of remaining distance over possible distance to be more accurate
                    list_dict_accumulations[list_current_reservoir[i_user]][list_current_mode[i_user]] -= \
                        accumulation_weights[i_user]
                    list_time_completion_legs[i_user][list_current_leg[i_user]] = time
                    completed_trips[i_user] = True
    print(completed_trips)
    return list_time_completion_legs, hist_accumulations, hist_speeds


if __name__ == "__main__":

    def res_fct1(dict_accumulations):
        V_car = 0
        if dict_accumulations['car'] < 18000:
            V_car = 11.5 - dict_accumulations['car'] * 6 / 18000
        elif dict_accumulations['car'] < 55000:
            V_car = 11.5 - 6 - (dict_accumulations['car'] - 18000) * 4.5 / (55000 - 18000)
        elif dict_accumulations['car'] < 80000:
            V_car = 11.5 - 6 - 4.5 - (dict_accumulations['car'] - 55000) * 1 / (80000 - 55000)
        V_car = max(V_car, 0.001)
        V_bus = 4
        dict_speeds = {'car': V_car, 'bus': V_bus}
        return dict_speeds


    def res_fct2(dict_accumulations):
        V_car = 11.5 * (1 - (dict_accumulations['car'] + dict_accumulations['bus']) / 80000)
        V_car = max(V_car, 0.001)
        V_bus = V_car/2
        dict_speeds = {'car': V_car, 'bus': V_bus}
        return dict_speeds


    Res1 = Reservoir(id=1, modes=['car', 'bus'], fct_MFD_speed=res_fct1)
    Res2 = Reservoir(id=2, modes=['car', 'bus'], fct_MFD_speed=res_fct2)

    departure_times = [700, 78]
    trip_legs = [[{'length': 1200, 'mode': 'car', 'sensor': 0}, {'length': 200, 'mode': 'bus', 'sensor': 0},
                  {'length': 2000, 'mode': 'bus', 'sensor': 1}],
                 [{'length': 2000, 'mode': 'car', 'sensor': 0}]]
    leg_times, hist_acc, hist_speeds = calculate_trip_times(departure_times, trip_legs, time_stop=1000, delta_t=30, accumulation_weights=[2000, 3000],
                                   list_reservoirs=[Res1, Res2])

    print('Test', hist_speeds)

    from matplotlib import pyplot as plt
    plt.figure()
    for i_res in range(2):
        for mode in ['car', 'bus']:
            plt.plot([x[i_res][mode] for x in hist_acc], label=mode+str(i_res))
    plt.title('Accumulation')
    plt.legend()
    plt.draw()

    plt.figure()
    for i_res in range(2):
        for mode in ['car', 'bus']:
            plt.plot([x[i_res][mode] for x in hist_speeds], label=mode+str(i_res))
    plt.title('Speed')
    plt.legend()
    plt.draw()