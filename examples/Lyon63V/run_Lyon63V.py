from mnms.simulation import Supervisor
from mnms.demand import CSVDemandManager
from mnms.flow.MFD import Reservoir, MFDFlowMotor
from mnms.log import attach_log_file, LOGLEVEL, set_mnms_logger_level, set_all_mnms_logger_level
from mnms.time import Time, Dt
from mnms.io.graph import load_graph, load_odlayer
from mnms.travel_decision.logit import LogitDecisionModel
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.public_transport import PublicTransportMobilityService

indir = "INPUTS"
outdir = "OUTPUTS"

set_all_mnms_logger_level(LOGLEVEL.INFO)
#set_mnms_logger_level(LOGLEVEL.INFO, ["mnms.simulation","mnms.mobility_service.public_transport"])
attach_log_file(outdir+'/simulation.log')

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
    #return {"CAR": V, "BUS":8,"METRO":40,"TRAM":15}
    return {"CAR": 12, "BUS": 8, "METRO": 25, "TRAM": 15}


if __name__ == '__main__':
    mmgraph = load_graph(indir + "/network-Lyon63V.json")

    odlayer = load_odlayer(indir + "/odlayer-Lyon63V.json")
    mmgraph.add_origin_destination_layer(odlayer)
    mmgraph.connect_origindestination_layers(250)

    veh_observer = CSVVehicleObserver(outdir+"/veh.csv")

    personal_car = PersonalMobilityService()
    personal_car.attach_vehicle_observer(veh_observer)
    mmgraph.layers["CAR"].add_mobility_service(personal_car)

    bus_service = PublicTransportMobilityService("BUS_MS")
    bus_service.attach_vehicle_observer(veh_observer)
    mmgraph.layers["BUSLayer"].add_mobility_service(bus_service)

    tram_service = PublicTransportMobilityService("TRAM_MS")
    tram_service.attach_vehicle_observer(veh_observer)
    mmgraph.layers["TRAMLayer"].add_mobility_service(tram_service)

    metro_service = PublicTransportMobilityService("METRO_MS")
    metro_service.attach_vehicle_observer(veh_observer)
    mmgraph.layers["METROLayer"].add_mobility_service(metro_service)

    mmgraph.connect_intra_layer("BUSLayer", 200)
    mmgraph.connect_inter_layers(["BUSLayer","TRAMLayer","METROLayer"],200)

    demand_file_name = indir + "/demand-Lyon63V-coords.csv"
    demand = CSVDemandManager(demand_file_name)
    demand.add_user_observer(CSVUserObserver(outdir+"/user.csv"), user_ids="all")

    flow_motor = MFDFlowMotor(outfile=outdir+"/flow.csv")

    for k, res in mmgraph.roads.zones.items():
        flow_motor.add_reservoir(Reservoir(res, ["CAR","BUS","TRAM","METRO"], calculate_V_MFD))

    travel_decision = LogitDecisionModel(mmgraph, outfile=outdir+"/path.csv", n_shortest_path=3)

    supervisor = Supervisor(graph=mmgraph,
                            flow_motor=flow_motor,
                            demand=demand,
                            decision_model=travel_decision,
                            outfile=outdir + "/travel_time_link.csv")

    supervisor.run(Time('06:30:00'), Time('10:30:00'), Dt(minutes=1), 10)
