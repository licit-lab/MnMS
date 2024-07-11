import pathlib

from mnms.generation.roads import *
from mnms.generation.layers import generate_layer_from_roads, generate_grid_origin_destination_layer
from mnms.graph.layers import MultiLayerGraph
from mnms.demand.manager import CSVDemandManager
from mnms.log import set_mnms_logger_level, LOGLEVEL, attach_log_file
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.mobility_service.on_demand import OnDemandMobilityService, OnDemandDepotMobilityService
from mnms.mobility_service.ride_hailing import *
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.time import Time, Dt
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
#from mnms.mobility_service.veh_distribution import generate_rh_supply_scenario, create_rh_veh_pos
from mnms.mobility_service.veh_generator import *
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.ride_hailing_Lyon import *
#from mnms.mobility_service.ride_hailing_Lyon_quick import *
#from mnms.mobility_service.print_statistics import *
#from mnms.mobility_service.ride_hailing_batch import *
# from mnms.mobility_service.test import *
from mnms.demand import User
import random
import matplotlib.pyplot as plt

from mnms.demand.user import Path
from mnms.generation.mlgraph import generate_manhattan_passenger_car
from mnms.generation.roads import generate_line_road
from mnms.tools.render import draw_roads, draw_path, draw_odlayer
import time
from datetime import timedelta
import os

start_time = time.monotonic()

set_mnms_logger_level(LOGLEVEL.INFO, ['mnms.simulation'])
# 'mnms.vehicles.veh_type',
# 'mnms.flow.user_flow',
# 'mnms.flow.MFD',
# 'mnms.layer.public_transport',
# 'mnms.travel_decision.model',
# 'mnms.tools.observer'])

# Params
radius = 4000
dt_matching = 2
# matching_strategy = 'nearest_idle_vehicle_in_radius_fifo'
matching_strategy = 'nearest_idle_vehicle_in_radius_batched'

# Graph
road_db = generate_manhattan_road(4, 3000)


#def run_sim(nb_veh = 150, idle_charge = 0, comp=True):
for nb_veh in [50,100,150,200]:
    for idle_charge in [0,1,2,3,4]:
        for comp in [True, False]:
            if comp:
                prefix = 'comp'
            else:
                prefix = 'coop'
            folder = prefix+str(nb_veh)+'_'+str(idle_charge)+'/'
            if not os.path.exists(folder):
                os.makedirs(folder)

            if comp:
                cwd = pathlib.Path(__file__).parent.joinpath('dem_gener_16reg_random_comp.csv').resolve()
            else:
                cwd = pathlib.Path(__file__).parent.joinpath('dem_gener_16reg_random_coop.csv').resolve()

            # Demand
            demand = CSVDemandManager(cwd)
            demand.add_user_observer(CSVUserObserver(folder + 'user.csv'))

            uber = RideHailingServiceLyon("UBER",
                                dt_matching = dt_matching,
                             matching_strategy = matching_strategy,
                             radius = radius)
            uber.attach_vehicle_observer(CSVVehicleObserver(folder+"veh_uber.csv"))
            uber.idle_km_or_h_charge = idle_charge

            lyft = RideHailingServiceLyon("LYFT",
                                          dt_matching=dt_matching,
                                          matching_strategy=matching_strategy,
                                          radius=radius)
            lyft.attach_vehicle_observer(CSVVehicleObserver(folder+"veh_lyft.csv"))
            lyft.idle_km_or_h_charge = idle_charge

            personal_car = PersonalMobilityService("PV")
            personal_car.attach_vehicle_observer(CSVVehicleObserver(folder+"veh_pv.csv"))

            car_layer = generate_layer_from_roads(road_db,
                                                  'CAR',
                                                  mobility_services=[personal_car, uber, lyft])

            odlayer = generate_grid_origin_destination_layer(0, 0, 12000, 12000, 4,
                                                             4)
            mlgraph = MultiLayerGraph([car_layer],
                                      odlayer,
                                      1e-3)


            if os.path.isfile('veh_locations_UBER' + str(nb_veh) + '.csv') and \
                os.path.isfile('veh_locations_LYFT' + str(nb_veh) + '.csv'):
                veh_read_uber(uber, nb_veh)
                veh_read_lyft(lyft, nb_veh)
            else:
                veh_generation(uber, nb_veh)
                veh_generation(lyft, nb_veh)

            # Decison Model

            decision_model = DummyDecisionModel(mlgraph, outfile=folder+"path.csv")
            decision_model.load_mobility_services_graphs_from_file("graph.json")

            def calculate_V_MFD(acc):
                V = 0  # data_coop from fit dsty
                N = acc["CAR"]
                if N < 1125:
                    V = 11.5 - N * 6 / 1125
                elif N < 3437.5:
                    V = 11.5 - 6 - (N - 1125) * 4.5 / (3437.5 - 1125)
                elif N < 5000:
                    V = 11.5 - 6 - 4.5 - (N - 3437.5) * 1 / (5000 - 3437.5)
                V = max(V, 0.001)  # min speed to avoid gridlock
                return {"CAR": V}


            flow_motor = MFDFlowMotor(outfile=folder+"MFD_info.csv")
            flow_motor.add_reservoir(Reservoir(road_db.zones["RES"], ['CAR'], calculate_V_MFD))

            supervisor = Supervisor(mlgraph,
                                    demand,
                                    flow_motor,
                                    decision_model,
                                    logfile="sim.log",
                                    loglevel=LOGLEVEL.INFO)

            supervisor.run(Time("16:59:00"),
                           Time("21:00:00"),
                           Dt(seconds=30),  # flow_dt is the timestep for moving the vehicles on the network,
                           1)  # flow_dt * affectation_factor corresponds to the timestep for updating the costs on the graph, and path choice for travelers

            end_time = time.monotonic()
            print("Elapsed time to run the program: ")
            print(timedelta(seconds=end_time - start_time))
