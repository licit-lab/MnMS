from mnms.simulation import Supervisor
from mnms.demand import CSVDemandManager
from mnms.flow.MFD import Reservoir, MFDFlow
from mnms.log import attach_log_file, LOGLEVEL, get_logger, set_all_mnms_logger_level, set_mnms_logger_level
from mnms.time import Time, Dt
from mnms.io.graph import load_graph
from mnms.travel_decision.logit import LogitDecisionModel
from mnms.tools.observer import CSVUserObserver
from mnms.generation.layers import generate_matching_origin_destination_layer
from mnms.mobility_service.car import PersonalCarMobilityService
from mnms.mobility_service.public_transport import PublicTransportMobilityService


import pandas as pd

indir = "INPUTS"
outdir = "OUTPUTS"

# set_all_mnms_logger_level(LOGLEVEL.WARNING)
set_mnms_logger_level(LOGLEVEL.INFO, ["mnms.simulation"])

#get_logger("mnms.graph.shortest_path").setLevel(LOGLEVEL.WARNING)
attach_log_file(outdir+'/simulation.log')

# 'DESTINATION_R_82604106' 'ORIGIN_E_83202447'

def create_lyon_grid_multimodal():
    lyon_file_name = indir + "/network_lyon6_V2.json"
    mmgraph = load_graph(lyon_file_name)
    return mmgraph

def calculate_V_MFD(acc):
    #V = 10.3*(1-N/57000) # data from fit prop
    V = 0 # data from fit dsty
    N = acc["CAR"]
    if N<18000:
        V=11.5-N*6/18000
    elif N<55000:
        V=11.5-6 - (N-18000)*4.5/(55000-18000)
    elif N<80000:
        V= 11.5-6-4.5-(N-55000)*1/(80000-55000)
    #V = 11.5*(1-N/60000)
    V = max(V,0.001) # min speed to avoid gridlock
    return {"CAR": V}


if __name__ == '__main__':
    mmgraph = create_lyon_grid_multimodal()

    odlayer = generate_matching_origin_destination_layer(mmgraph.roaddb)
    mmgraph.connect_origin_destination_layer(odlayer, 1e-3)


    mmgraph.layers["CAR"].add_mobility_service(PersonalCarMobilityService())
    # mmgraph.layers["BUSLayer"].add_mobility_service(PublicTransportMobilityService("BUS"))
    # mmgraph.layers["TRAMLayer"].add_mobility_service(PublicTransportMobilityService("TRAM"))
    # mmgraph.layers["METROLayer"].add_mobility_service(PublicTransportMobilityService("METRO"))
    # from hipop.shortest_path import dijkstra
    #
    # path = dijkstra(mmgraph.graph, 'ORIGIN_R_82607470', 'DESTINATION_S_82618270_T_724107724_FRef', "length")
    # print(path)


    demand_file_name = indir + "/demand2.csv"
    demand = CSVDemandManager(demand_file_name, demand_type='node')
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