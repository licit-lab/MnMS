import random
import pandas as pd
import os


def veh_generation(rh_service, nb_veh):

    # create a certain number of vehicle at random positions of the network:
    location = []
    company = []

    for i in range(0, nb_veh):
        keep_looping = True
        n = None
        while keep_looping:
            n = random.choice(list(rh_service.graph.nodes))
            for n2 in rh_service.graph.nodes.values():
                if n == n2.id:
                    if (0 <= n2.position[0] <= 10000) and (0 <= n2.position[1] <= 10000):
                        rh_service.create_waiting_vehicle(n2.id)
                        location.append(n2.id)
                        company.append(rh_service.id)
                        keep_looping = False

    veh_data = {
        "LOCATION": location,
        "SERVICE": company
    }
    df = pd.DataFrame(veh_data)
    name = 'veh_locations_' + str(rh_service.id) + str(nb_veh) + '.csv'
    df.to_csv(name, mode='w', sep=';', index=False)

def veh_read_uber(rh_service, nb_veh):
    df = pd.read_csv('veh_locations_UBER'+str(nb_veh)+'.csv', sep=';')
    #df = pd.read_csv('/Users/maryia/Documents/GitHub/MnMS/examples/my_example/vehicles/' + veh + '_veh_locations_UBER.csv', sep=';')
    for i in range(len(df)):
        if df.loc[i, "SERVICE"] == rh_service.id:
            rh_service.create_waiting_vehicle(df.loc[i, "LOCATION"])

def veh_read_lyft(rh_service, nb_veh):
    df = pd.read_csv('veh_locations_LYFT'+str(nb_veh)+'.csv', sep=';')
    #df = pd.read_csv('/Users/maryia/Documents/GitHub/MnMS/examples/my_example/vehicles/' + veh + '_veh_locations_LYFT.csv', sep=';')
    for i in range(len(df)):
        if df.loc[i, "SERVICE"] == rh_service.id:
            rh_service.create_waiting_vehicle(df.loc[i, "LOCATION"])
