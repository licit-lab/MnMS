import json
import os
import pathlib
from pathlib import Path

from mnms.database.settings import DbSettings
from mnms.day_to_day import EnumMethod, DayToDayParameters, run_day_to_day
from mnms.graph.layers import MultiLayerGraph
from mnms.io.graph import load_graph, load_odlayer
from mnms.demand.manager import CSVDemandManager
from mnms.flow.MFD import MFDFlow, Reservoir
from mnms.log import set_mnms_logger_level, LOGLEVEL
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.time import Time, Dt
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver

set_mnms_logger_level(LOGLEVEL.INFO, ['mnms.simulation'])

cwd = pathlib.Path(__file__).parent.resolve()
inputs_folder = cwd.joinpath("INPUTS")
outputs_folder = cwd.joinpath("OUTPUTS")


def create_graph(inputs_folder: Path) -> MultiLayerGraph:
    mlgraph = load_graph(inputs_folder.joinpath("manhattan_20x20.json"))
    odlayer = load_odlayer(inputs_folder.joinpath("odlayer_20x20.json"))
    mlgraph.layers['CAR'].mobility_services['PersonalCar'].attach_vehicle_observer(CSVVehicleObserver("veh.csv"))
    mlgraph.connect_origin_destination_layer(odlayer, 1e-5)
    return mlgraph


def create_decision_model(
        mlgraph: MultiLayerGraph, outputs_folder: Path) -> DummyDecisionModel:
    return DummyDecisionModel(mlgraph, outfile=outputs_folder.joinpath('path.csv'))


# Flow Motor
def create_flow_motor():
    def mfd_outer(dacc):
        dict_speed = {'CAR': 20}
        return dict_speed

    def mfd_inner(dacc):
        n_car = dacc['CAR']
        if n_car > 0:
            dict_speed = {'CAR': 1}
        else:
            dict_speed = {'CAR': 20}
        return dict_speed

    flow_motor = MFDFlow(outfile='flow.csv')
    flow_motor.add_reservoir(Reservoir('up', ['CAR'], mfd_outer))
    flow_motor.add_reservoir(Reservoir('middle', ['CAR'], mfd_inner))
    flow_motor.add_reservoir(Reservoir('down', ['CAR'], mfd_outer))
    return flow_motor


def create_demand(
        inputs_folder: Path, outputs_folder: Path) -> CSVDemandManager:
    demand = CSVDemandManager(inputs_folder.joinpath("demand.csv"))
    demand.add_user_observer(CSVUserObserver(outputs_folder.joinpath('user.csv')))
    return demand


param_file_path = "./param.json"
param_file = open(os.getcwd() + param_file_path, 'r')
param_json = json.load(param_file)

DbSettings().load_from_dict(param_json["DAY_TO_DAY"])


parameters = DayToDayParameters(
    method=EnumMethod.FIFTY_PERCENT,
    number_of_days=5,
    create_graph=create_graph,
    create_decision_model=create_decision_model,
    create_flow_motor=create_flow_motor,
    create_demand=create_demand,
    inputs_folder=inputs_folder,
    outputs_folder=outputs_folder,
    tstart=Time("07:00:00"),
    tend=Time("07:30:00"),
    flow_dt=Dt(minutes=1),
    affectation_factor=10)

run_day_to_day(parameters)
