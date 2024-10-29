from mnms.simulation import Supervisor, load_snaphshot
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

if __name__ == '__main__':

    outdir = "OUTPUTS"

    # Outputs
    outdir_path = os.getcwd() + '/' + outdir
    if not os.path.isdir(outdir_path):
        os.mkdir(outdir_path)

    set_all_mnms_logger_level(LOGLEVEL.INFO)
    get_logger("mnms.graph.shortest_path").setLevel(LOGLEVEL.WARNING)
    attach_log_file(outdir_path + '/simulation.log')

    supervisor = load_snaphshot(outdir_path+'/snapshot')

    supervisor.run(Time('08:30:00'), Time('08:45:00'), Dt(seconds=1), 10)