from mnms.simulation import Supervisor
from mnms.generation.roads import generate_line_road
from mnms.graph.layers import MultiLayerGraph, CarLayer
from mnms.flow.MFD import Reservoir, MFDFlowMotor
from mnms.log import attach_log_file, LOGLEVEL, get_logger, set_all_mnms_logger_level
from mnms.time import Time, Dt
from mnms.travel_decision.logit import LogitDecisionModel
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.graph.specific_layers import OriginDestinationLayer
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.demand import BaseDemandManager, User
from mnms.graph.zone import Zone, construct_zone_from_sections
from mnms.io.graph import save_graph
import logging
import pandas as pd
import os

def mfdspeed(dacc):
    dspeed = {'CAR': 13.8}
    return dspeed

if __name__ == '__main__':

    outdir = "OUTPUTS"

    # Outputs
    outdir_path = os.getcwd() + '/' + outdir
    if not os.path.isdir(outdir_path):
        os.mkdir(outdir_path)

    set_all_mnms_logger_level(LOGLEVEL.INFO)
    get_logger("mnms.graph.shortest_path").setLevel(LOGLEVEL.WARNING)
    attach_log_file(outdir_path + '/simulation.log')

    # Network creation
    roads = generate_line_road([0,0], [1500,0], 2, 'Z')

    pv = PersonalMobilityService()
    pv.attach_vehicle_observer(CSVVehicleObserver(outdir_path+"/veh.csv"))
    car_layer = CarLayer(roads, services=[pv])

    car_layer.create_node("CAR_0", "0")
    car_layer.create_node("CAR_1", "1")
    car_layer.create_link("CAR_0_1", "CAR_0", "CAR_1", {}, ["0_1"])
    car_layer.create_link("CAR_1_0", "CAR_1", "CAR_0", {}, ["1_0"])

    odlayer = OriginDestinationLayer()
    odlayer.create_origin_node('O',[-200,0])
    odlayer.create_destination_node('D',[1700,0])

    mlgraph = MultiLayerGraph([car_layer],
                              odlayer,
                              250)

    # Demand
    demand = BaseDemandManager([User("U0", [-230, 0], [1730, 0], Time("08:16:00"))])
    demand.add_user_observer(CSVUserObserver(outdir_path+"/user.csv"), user_ids="all")

    flow_motor = MFDFlowMotor(outfile=outdir_path+"/flow.csv")

    flow_motor.add_reservoir(Reservoir(roads.zones["Z"], ['CAR'], mfdspeed))

    travel_decision = LogitDecisionModel(mlgraph, outfile=outdir_path+"/path.csv",verbose_file=True)

    save_graph(mlgraph, outdir_path+'/monolink.json')

    supervisor = Supervisor(graph=mlgraph,
                            flow_motor=flow_motor,
                            demand=demand,
                            decision_model=travel_decision,
                            outfile=outdir_path + "/travel_time_link.csv")

    supervisor.run(Time('08:15:00'), Time('08:30:00'), Dt(seconds=1), 10, snapshot=True, snapshot_folder=outdir_path)