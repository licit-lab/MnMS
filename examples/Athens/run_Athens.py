######################################################
#   Python file created by Arthur Labbaye (intern)
#
#   Creation date: November 2023
#
#   Description: Program allowing you to launch the
#   MnMs simulation for the city of Athens.
######################################################
from mnms.generation.layers import generate_matching_origin_destination_layer, generate_grid_origin_destination_layer
from mnms.io.graph import load_graph, load_odlayer
from mnms.demand.manager import CSVDemandManager
from mnms.log import set_mnms_logger_level, LOGLEVEL
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.travel_decision.logit import LogitDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.time import Time, Dt
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.graph.layers import MultiLayerGraph

import numpy as np
import pathlib

# parameters
indir = 'inputs/'
outdir = 'outputs/'





set_mnms_logger_level(LOGLEVEL.INFO, ['mnms.simulation',
                                      'mnms.vehicles.veh_type',
                                      'mnms.flow.user_flow',
                                      'mnms.flow.MFD',
                                      'mnms.layer.public_transport',
                                      'mnms.travel_decision.model',
                                      'mnms.tools.observer'])

#cwd = pathlib.Path(__file__).parent.joinpath('in_files/demand7h9h_1000m.csv').resolve()

# import of the network file
#loaded_mlgraph = load_graph(indir+"mlgraph_PT_CAR.json")
loaded_mlgraph = load_graph(indir+"mlgraph_tc_car.json")

# creation and connection of the odlayer
odlayer = load_odlayer(indir+"odlayer_clustered")
#odlayer = generate_matching_origin_destination_layer(mlgraph.roads)

# Mobility services
car_layer = loaded_mlgraph.layers['CAR']
car_service = car_layer.mobility_services['PersonalVehicle']
car_service.attach_vehicle_observer(CSVVehicleObserver(outdir + 'car.csv'))

tram_layer = loaded_mlgraph.layers['TRAM']
tram_service = tram_layer.mobility_services['TRAM']
tram_service.attach_vehicle_observer(CSVVehicleObserver(outdir + 'tram.csv'))

metro_layer = loaded_mlgraph.layers['METRO']
metro_service = metro_layer.mobility_services['METRO']
metro_service.attach_vehicle_observer(CSVVehicleObserver(outdir + 'metro.csv'))

mlgraph = MultiLayerGraph([car_layer, tram_layer, metro_layer],
                          odlayer, connection_distance=500)

# import of the demand file
#demand = CSVDemandManager(indir+"demand_7h9h_1000m.csv")
demand = CSVDemandManager(indir+"demand_filtered.csv")
decision_model = DummyDecisionModel(mlgraph, outfile=outdir+"path.csv")
#decision_model = LogitDecisionModel(mlgraph, theta=1, n_shortest_path=5, outfile=outdir+"path.csv")

# definition of the MFD function
# MFD based on the network length, not on traffic measurements, see Arthur's report
coeff = [-1.15306038e-13, 1.35397002e-08, -5.71693912e-04, 9.46587343e+00]
poly_func = np.poly1d(coeff)
def mfdspeed(acc):
    N = acc["CAR"]
    speed_car = poly_func(N)
    dspeed = {'CAR': max(speed_car, 0.01)}
    return dspeed

flow_motor = MFDFlowMotor(outfile=outdir+"flow.csv")
flow_motor.add_reservoir(Reservoir(mlgraph.roads.zones["RES"], ['CAR'], mfdspeed))

# launch of the simulation
supervisor = Supervisor(mlgraph,
                        demand,
                        flow_motor,
                        decision_model)

supervisor.run(Time("07:00:00"),
               Time("09:30:00"),
               Dt(seconds=30),
               1)
