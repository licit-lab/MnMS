import argparse
import json
from pathlib import Path
from typing import Any

from mnms.demand import CSVDemandManager
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.generation.layers import generate_matching_origin_destination_layer
from mnms.io.graph import load_graph, save_graph
from mnms.log import LOGLEVEL, attach_log_file, set_mnms_logger_level
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.simulation import Supervisor
from mnms.time import Dt, Time
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.travel_decision.logit import LogitDecisionModel


class Lyon6Parameters:
    """Load and provide access to a Lyon6 simulation configuration."""

    _SECTIONS = (
        "INPUT",
        "OUTPUT",
        "SUPERVISOR",
        "RESERVOIRS",
        "GRAPH",
        "COSTS",
        "TRAVEL_DECISION",
    )

    def __init__(self, config_file: str | Path) -> None:
        self.config_file = Path(config_file).expanduser().resolve()
        with self.config_file.open(encoding="utf-8") as parameter_file:
            config = json.load(parameter_file)

        for section_name in self._SECTIONS:
            section = config.get(section_name)
            if not isinstance(section, (dict, list)):
                raise ValueError(
                    f"Missing or invalid '{section_name}' section in {self.config_file}"
                )
            setattr(self, section_name.lower(), section)

    def _resolve_path(self, base_directory: str, configured_path: str) -> Path:
        path = Path(configured_path.lstrip("/\\"))
        return (self.config_file.parent / base_directory / path).resolve()

    @property
    def input_directory(self) -> Path:
        return self._resolve_path("", self.input["indir"])

    @property
    def output_directory(self) -> Path:
        return self._resolve_path("", self.output["output_dir"])

    def input_path(self, configured_path: str) -> Path:
        return self._resolve_path(self.input["indir"], configured_path)

    def output_path(self, configured_path: str) -> Path:
        return self._resolve_path(self.output["output_dir"], configured_path)

    @property
    def network_file_with_roadstypo(self) -> Path:
        network_path = self.input_path(self.input["network_file"])
        return network_path.with_name(f"{network_path.stem}_roadstypo{network_path.suffix}")

    @property
    def log_level(self) -> int:
        configured_level = self.supervisor["log_level"].removeprefix("LOGLEVEL.")
        try:
            return getattr(LOGLEVEL, configured_level)
        except AttributeError as error:
            raise ValueError(f"Unknown log level: {self.supervisor['log_level']}") from error


def calculate_V_MFD(acc: dict[str, float]) -> dict[str, float]:
    accumulation = acc["CAR"]
    if accumulation < 18_000:
        speed = 11.5 - accumulation * 6 / 18_000
    elif accumulation < 55_000:
        speed = 11.5 - 6 - (accumulation - 18_000) * 4.5 / (55_000 - 18_000)
    elif accumulation < 80_000:
        speed = 11.5 - 6 - 4.5 - (accumulation - 55_000) / (80_000 - 55_000)
    else:
        speed = 0
    return {"CAR": max(speed, 0.001)}


def make_weighted_travel_time_car(
    roads_typo_cost_multipliers: dict[str, float],
):
    def weighted_travel_time_car(gnodes: Any, layer: Any, link: Any, costs: dict) -> float:
        link_class = layer.map_links_classes.get(link.id)
        travel_time = costs["PersonalVehicle"]["travel_time"]
        multiplier = roads_typo_cost_multipliers.get(link_class)
        return travel_time * multiplier if multiplier is not None else travel_time

    return weighted_travel_time_car


def weighted_travel_time_transit(gnodes: Any, layer: Any, link: Any, costs: dict) -> float:
    return costs["WALK"]["travel_time"]


def run_simulation(parameters: Lyon6Parameters) -> None:

    parameters.output_directory.mkdir(parents=True, exist_ok=True)
    set_mnms_logger_level(parameters.log_level, ["mnms.simulation"])
    attach_log_file(str(parameters.output_path(parameters.output["log_file"])))

    network_path = parameters.input_path(parameters.input["network_file"])
    mmgraph = load_graph(str(network_path))
    if mmgraph.layers["CAR"].map_links_classes == {}:
        mmgraph.layers["CAR"].add_links_classes(parameters.graph["roads_typo"])
        save_graph(mmgraph, str(parameters.network_file_with_roadstypo))

    odlayer = generate_matching_origin_destination_layer(mmgraph.roads)
    mmgraph.add_origin_destination_layer(odlayer)
    mmgraph.connect_origindestination_layers(1e-3)

    personal_car = PersonalMobilityService()
    personal_car.attach_vehicle_observer(
        CSVVehicleObserver(str(parameters.output_path(parameters.output["vehicle_file"])))
    )
    mmgraph.layers["CAR"].add_mobility_service(personal_car)

    cost_name = parameters.costs["cost"]
    mmgraph.add_cost_function(
        "CAR",
        cost_name,
        make_weighted_travel_time_car(parameters.costs["roads_typo_cost_multipliers"]),
        mobility_service="PersonalVehicle",
    )
    mmgraph.add_cost_function("TRANSIT", cost_name, weighted_travel_time_transit)

    demand = CSVDemandManager(str(parameters.input_path(parameters.input["demand_file"])))
    demand.add_user_observer(
        CSVUserObserver(str(parameters.output_path(parameters.output["user_file"]))),
        user_ids="all",
    )

    flow_motor = MFDFlowMotor(
        outfile=str(parameters.output_path(parameters.output["flow_file"]))
    )
    flow_motor.add_reservoir(Reservoir(mmgraph.roads.zones["RES"], ["CAR"], calculate_V_MFD))

    decision_model = parameters.travel_decision["decision_model"]
    decision_models = {
        "LogitDecisionModel": LogitDecisionModel,
        "DummyDecisionModel": DummyDecisionModel,
    }
    try:
        decision_model_class = decision_models[decision_model]
    except KeyError as error:
        raise ValueError(f"Unknown decision model {decision_model}") from error

    travel_decision = decision_model_class(
        mmgraph,
        cost=cost_name,
        outfile=str(parameters.output_path(parameters.output["path_file"])),
        verbose_file=True,
    )
    travel_decision.add_waiting_cost_function(cost_name, lambda waiting_time: waiting_time)

    supervisor = Supervisor(
        graph=mmgraph,
        flow_motor=flow_motor,
        demand=demand,
        decision_model=travel_decision,
        outfile=str(parameters.output_path(parameters.output["travel_time_file"])),
    )
    supervisor_params = parameters.supervisor
    supervisor.run(
        Time(supervisor_params["start_time"]),
        Time(supervisor_params["end_time"]),
        Dt(minutes=supervisor_params["flow_dt"]),
        supervisor_params["affectation_factor"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Lyon6 simulation.")
    parser.add_argument(
        "config_file",
        nargs="?",
        type=Path,
        default=Path(__file__).with_name("param.json"),
        help="path to the JSON parameter file (defaults to param.json)",
    )
    arguments = parser.parse_args()
    run_simulation(Lyon6Parameters(arguments.config_file))
    