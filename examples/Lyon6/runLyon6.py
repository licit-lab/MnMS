from mnms.simulation import Supervisor
from mnms.demand import CSVDemandManager
from mnms.flow.MFD import Reservoir, MFDFlow
from mnms.log import attach_log_file, LOGLEVEL, get_logger, set_all_mnms_logger_level, set_mnms_logger_level
from mnms.time import Time, Dt
from mnms.io.graph import load_graph
from mnms.travel_decision.logit import LogitDecisionModel
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.generation.layers import generate_matching_origin_destination_layer
from mnms.mobility_service.car import PersonalCarMobilityService
from mnms.mobility_service.public_transport import PublicTransportMobilityService


indir = "INPUTS"
outdir = "OUTPUTS"

set_mnms_logger_level(LOGLEVEL.INFO, ["mnms.simulation"])

attach_log_file(outdir+'/simulation.log')


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
    mmgraph = load_graph(indir + "/network_lyon6_V2.json")

    odlayer = generate_matching_origin_destination_layer(mmgraph.roads)
    mmgraph.connect_origin_destination_layer(odlayer, 1e-3)

    personal_car = PersonalCarMobilityService()
    personal_car.attach_vehicle_observer(CSVVehicleObserver(outdir+"/veh.csv"))
    mmgraph.layers["CAR"].add_mobility_service(personal_car)

    demand_file_name = indir + "/demand_coords.csv"
    demand = CSVDemandManager(demand_file_name)
    demand.add_user_observer(CSVUserObserver(outdir+"/user.csv"), user_ids="all")

    flow_motor = MFDFlow(outfile=outdir+"/flow.csv")
    flow_motor.add_reservoir(Reservoir("RES", ["CAR"], calculate_V_MFD))

    travel_decision = LogitDecisionModel(mmgraph, outfile=outdir+"/path.csv")

    supervisor = Supervisor(graph=mmgraph,
                            flow_motor=flow_motor,
                            demand=demand,
                            decision_model=travel_decision,
                            outfile=outdir + "/travel_time_link.csv")

    supervisor.run(Time('00:00:00'), Time('00:30:00'), Dt(minutes=1), 10)
    
