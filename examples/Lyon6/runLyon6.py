from mnms.simulation import Supervisor
from mnms.demand import CSVDemandManager
from mnms.flow.MFD import Reservoir, MFDFlowMotor
from mnms.log import attach_log_file, LOGLEVEL, get_logger, set_all_mnms_logger_level, set_mnms_logger_level
from mnms.time import Time, Dt
from mnms.io.graph import load_graph
from mnms.travel_decision.logit import LogitDecisionModel
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.generation.layers import generate_matching_origin_destination_layer
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.public_transport import PublicTransportMobilityService

import os
import json

param_file_path = "data/param.json"
param_file = open(os.getcwd() + param_file_path, 'r')
param_json = json.load(param_file)

# Get Json parameters blocs
input_params = param_json['INPUT'] # bloc with input parameters
output_params = param_json['OUTPUT'] # bloc with output parameters
supervisor_params = param_json['SUPERVISOR'] # bloc with supervisor parameters
reservoirs_params = param_json['RESERVOIRS'] # bloc with reservoirs parameters
travel_decision_params = param_json['TRAVEL_DECISION'] # bloc with travel decision parameters

param_file.close()

# Get Json parameters

# inputs
indir = input_params['indir'] # name of input folder, ex: "INPUTS"
network_file = input_params['network_file'] # path to json network file, ex: "/Lyon_symuviainput.json"
demand_file = input_params['demand_file'] # path to csv demand file 
mfd_file = input_params['mfd_file'] # path to csv MFD file
# outputs
outdir = output_params['output_dir'] # name of output folder, ex: "OUTPUTS"
log_file = output_params['log_file'] # path to log file, ex: "/simulation.log"
path_file = output_params['path_file'] # path to csv path file
user_file = output_params['user_file'] # path to csv user file
flow_file = output_params['flow_file'] # path to csv flow file
travel_time_file = output_params['travel_time_file'] # path to csv travel time file
vehicle_file = output_params['vehicle_file']
# supervisor
log_level = supervisor_params['log_level'] # log level, ex: "LOGLEVEL.WARNING"
demand_type = supervisor_params['demand_type'] # demand type, "node" or "coordinate"
start_time = supervisor_params['start_time'] # start time in the simulation, ex: "06:30:00"
end_time = supervisor_params['end_time'] # end time in the simulation, ex: "14:00:00"
flow_dt = supervisor_params['flow_dt'] # simulation step, ex: 1 (unit in unit_flow_dt parameter)
unit_flow_dt = supervisor_params['unit_flow_dt'] # unit of the simulation step, ex: "minutes"
affectation_factor = supervisor_params['affectation_factor'] # affectation/calculation factor, ex: 10, 10 means 10 * flow_dt so 10 minutes
# reservoirs

# travel_decision
n_shortest_path = travel_decision_params['n_shortest_path'] # number of shortest path calculated
radius_sp = travel_decision_params['radius_sp'] # first radius for node search in shortest path calculation
radius_growth_sp = travel_decision_params['radius_growth_sp'] # radius step for node search in sp calculation
walk_speed = travel_decision_params['walk_speed'] # walking speed, ex: 1.4 (meter per second?)
scale_factor_sp = travel_decision_params['scale_factor_sp'] # 
algorithm = travel_decision_params['algorithm'] # algorithm used for shortest path calculation, ex: "astar" or "djikstra"
decision_model = travel_decision_params['decision_model'] # decision model used, ex: "LogitDecisionModel"
available_mobility_services = travel_decision_params['available_mobility_services'] # list with available mobility services ex: ["WALK", "PersonalCar"]




set_mnms_logger_level(LOGLEVEL.INFO, ["mnms.simulation"])

attach_log_file(outdir+log_file)


def calculate_V_MFD(acc):
    V = 0  # data from fit dsty
    N = acc["CAR"]
    if N < 18000:
        V = 11.5-N*6/18000
    elif N < 55000:
        V = 11.5-6 - (N-18000)*4.5/(55000-18000)
    elif N < 80000:
        V = 11.5-6-4.5-(N-55000)*1/(80000-55000)
    V = max(V, 0.001)  # min speed to avoid gridlock
    return {"CAR": V}


if __name__ == '__main__':
    mmgraph = load_graph(indir+network_file)

    odlayer = generate_matching_origin_destination_layer(mmgraph.roads)
    mmgraph.add_origin_destination_layer(odlayer)
    mmgraph.connect_origin_destination_layer(1e-3)

    personal_car = PersonalMobilityService()
    personal_car.attach_vehicle_observer(CSVVehicleObserver(outdir+vehicle_file))
    mmgraph.layers["CAR"].add_mobility_service(personal_car)

    demand_file_name = indir + demand_file
    demand = CSVDemandManager(demand_file_name)
    demand.add_user_observer(CSVUserObserver(outdir+user_file), user_ids="all")

    flow_motor = MFDFlowMotor(outfile=outdir + flow_file)
    flow_motor.add_reservoir(Reservoir(mmgraph.roads.zones["RES"], ["CAR"], calculate_V_MFD))

    travel_decision = LogitDecisionModel(mmgraph, outfile=outdir+path_file)

    supervisor = Supervisor(graph=mmgraph,
                            flow_motor=flow_motor,
                            demand=demand,
                            decision_model=travel_decision,
                            outfile=outdir+travel_time_file)

    supervisor.run(Time(start_time), Time(end_time), Dt(minutes=flow_dt), affectation_factor)


