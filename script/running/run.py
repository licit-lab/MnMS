import argparse
import json
import math
from functools import partial
from pathlib import Path
from typing import Any

from mnms.demand import CSVDemandManager
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.io.graph import load_graph, load_odlayer
from mnms.log import LOGLEVEL, attach_log_file, set_mnms_logger_level
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.simulation import Supervisor
from mnms.time import Dt, Time
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.travel_decision.logit import LogitDecisionModel


class MnMSParameters:
    """Load and provide access to a MnMS simulation configuration."""

    _SECTIONS = (
        "GRAPH",
        "DEMAND",
        "FLOW_MOTOR",
        "DECISION_MODEL",
        "SCENARIO"
    )

    def __init__(self, config_file: str | Path) -> None:
        self.config_file = Path(config_file).expanduser().resolve()
        with self.config_file.open(encoding="utf-8") as parameter_file:
            config = json.load(parameter_file)

        for section_name in self._SECTIONS:
            section = config.get(section_name)
            if not isinstance(section, (dict, list)):
                raise ValueError(  # noqa: TRY004
                    f"Missing or invalid '{section_name}' section in {self.config_file}"
                )
            setattr(self, section_name.lower(), section)

    def _resolve_path(self, base_directory: str, configured_path: str) -> Path:
        path = Path(configured_path.lstrip("/\\"))
        return (self.config_file.parent / base_directory / path).resolve()

    # GRAPH
    @property
    def network_file(self) -> str:
        return str(self._resolve_path("", self.graph["network_file"]))

    # OD_LAYER
    @property
    def odlayer_file(self) -> str:
        return str(self._resolve_path("", self.graph["OD_LAYER"]["file"]))

    @property
    def odlayer_connection_distance(self) -> float:
        return self.graph["OD_LAYER"]["connection_distance"]

    @property
    def mobility_services(self) -> list[dict]:
        return self.graph.get("MOBILITY_SERVICES", [])

    @property
    def intra_layer_connections(self) -> list[dict]:
        return self.graph.get("CONNECTION_INTRA_LAYER", [])

    @property
    def inter_layers_connections(self) -> list[dict]:
        return self.graph.get("CONNECTION_INTER_LAYERS", [])

    # DEMAND
    @property
    def demand_file(self) -> str:
        return str(self._resolve_path("", self.demand["file"]))

    # FLOW_MOTOR
    @property
    def MFD_parameters(self) -> list[dict[str, Any]]:
        return self.flow_motor.get("MFD", [])

    # DECISION_MODEL
    @property
    def decision_model_type(self) -> str:
        return self.decision_model.get("model", "logit")

    @property
    def decision_model_nb_shortest_paths(self) -> int:
        return self.decision_model.get("n_shortest_path", 3)

    # SCENARIO
    @property
    def start_time(self) -> Time:
        return Time(self.scenario["start"])

    @property
    def end_time(self) -> Time:
        return Time(self.scenario["end"])

    @property
    def flow_timestep(self) -> Dt:
        return Dt(seconds=self.scenario["flow_timestep"])

    @property
    def assignment_factor(self) -> int:
        return self.scenario.get("assignment_factor", 10)

    @property
    def output_directory(self) -> Path:
        return self._resolve_path("", self.scenario["output_dir"])

    def output_path(self, configured_path: str) -> Path:
        return self._resolve_path(self.scenario["output_dir"], configured_path)

    @property
    def log_level(self) -> int:
        configured_level = self.scenario["logger_level"].removeprefix("LOGLEVEL.")
        try:
            return getattr(LOGLEVEL, configured_level)
        except AttributeError as error:
            raise ValueError(f"Unknown log level: {self.supervisor['log_level']}") from error


def calculate_speed_from_MFD(
    accumulations: dict[str, float],
    mfd_by_mode: dict[str, list[dict[str, Any]]],
) -> dict[str, float]:
    speeds = {}
    for mode, ranges in mfd_by_mode.items():
        accumulation = accumulations.get(mode, 0)
        for accumulation_range in ranges:
            minimum = float(accumulation_range["min"])
            maximum_value = accumulation_range["max"]
            maximum = math.inf if maximum_value == "inf" else float(maximum_value)
            if minimum <= accumulation <= maximum:
                speeds[mode] = (
                    float(accumulation_range["slope"]) * accumulation
                    + float(accumulation_range["intercept"])
                )
                break
        else:
            raise ValueError(
                f"No MFD accumulation range configured for mode '{mode}' "
                f"at accumulation {accumulation}"
            )
    return speeds


def _mfd_parameters_by_mode(
    reservoir_id: str,
    mfd_parameters: list[dict[str, Any]],
    layers: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    mfd_by_mode = {}
    for reservoir_parameters in mfd_parameters:
        if reservoir_parameters.get("reservoir_id") != reservoir_id:
            continue

        layer_parameters = reservoir_parameters.get(
            "MFD", reservoir_parameters.get("MFD_param", [])
        )
        for layer_parameter in layer_parameters:
            layer_name = layer_parameter["layer"]
            if layer_name not in layers:
                raise ValueError(
                    f"MFD configuration for reservoir '{reservoir_id}' "
                    f"references unknown layer '{layer_name}'"
                )

            mode = layers[layer_name]._veh_type.__name__.upper()
            ranges = layer_parameter["acc_ranges"]
            if mode in mfd_by_mode and mfd_by_mode[mode] != ranges:
                raise ValueError(
                    f"Conflicting MFD configuration for mode '{mode}' "
                    f"in reservoir '{reservoir_id}'"
                )
            mfd_by_mode[mode] = ranges

    if not mfd_by_mode:
        raise ValueError(f"No MFD configuration found for reservoir '{reservoir_id}'")
    return mfd_by_mode


def run_simulation(parameters: MnMSParameters) -> None:

    parameters.output_directory.mkdir(parents=True, exist_ok=True)
    set_mnms_logger_level(parameters.log_level, ["mnms.simulation"])
    attach_log_file(str(parameters.output_path("log.log")))

    veh_observer = CSVVehicleObserver(str(parameters.output_path("veh.csv")))

    # Create the graph from the network file
    print(f"Loading graph from {parameters.network_file}...")
    mmgraph = load_graph(parameters.network_file)

    # Add the origin-destination layer
    print(f"Loading OD layer from {parameters.odlayer_file}...")
    odlayer = load_odlayer(parameters.odlayer_file)
    mmgraph.add_origin_destination_layer(odlayer)
    mmgraph.connect_origindestination_layers(parameters.odlayer_connection_distance)

    # Create the mobility services
    print("Creating mobility services...")
    for ms in parameters.mobility_services:
        layer_name = ms["layer"]
        if layer_name not in mmgraph.layers:
            raise ValueError(f"Layer '{layer_name}' not found in the graph.")
        else:
            ms_type = ms["mobility_service_type"]
            if ms_type == "PersonalMobilityService":
                mobility_service = PersonalMobilityService()
            elif ms_type == "PublicTransportMobilityService":
                mobility_service = PublicTransportMobilityService(ms["label"])
            else:
                raise ValueError(f"Unknown mobility service type: {ms_type}")

            # Attach the mobility service to the corresponding layer
            layer_name = ms["layer"]
            mmgraph.layers[layer_name].add_mobility_service(mobility_service)

            mobility_service.attach_vehicle_observer(veh_observer)

    # Connect the layers (intra-layer and inter-layer connections)
    print("Connecting layers...")
    for conn in parameters.intra_layer_connections:
        mmgraph.connect_intra_layer(conn["layer"], conn["connection_distance"])

    for conn in parameters.inter_layers_connections:
        mmgraph.connect_inter_layers(conn["layers"], conn["connection_distance"])

    # Load demand and create the demand manager
    print
    demand = CSVDemandManager(parameters.demand_file)
    demand.add_user_observer(CSVUserObserver(str(parameters.output_path("user.csv"))), user_ids="all")

    # Create the flow motor and add reservoirs
    print("Creating flow motor...")
    flow_motor = MFDFlowMotor(outfile=str(parameters.output_path("flow.csv")))

    for res in mmgraph.roads.zones.values():
        mfd_by_mode = _mfd_parameters_by_mode(
            res.id, parameters.MFD_parameters, mmgraph.layers
        )
        mfd_speed = partial(calculate_speed_from_MFD, mfd_by_mode=mfd_by_mode)
        flow_motor.add_reservoir(Reservoir(res, list(mfd_by_mode), mfd_speed))

    # Create the travel decision model
    print(f"Creating decision model of type '{parameters.decision_model_type}'...")
    if parameters.decision_model_type == "logit":
        decision_model_class = LogitDecisionModel
    elif parameters.decision_model_type == "dummy":
        decision_model_class = DummyDecisionModel
    else:
        raise ValueError(f"Unknown decision model: {parameters.decision_model_type}")

    decision_model = decision_model_class(
        mmgraph,
        outfile=str(parameters.output_path("path.csv")),
        n_shortest_path=parameters.decision_model_nb_shortest_paths,
    )

    # Create the supervisor
    print("Creating supervisor...")
    supervisor = Supervisor(
        graph=mmgraph,
        flow_motor=flow_motor,
        demand=demand,
        decision_model=decision_model,
        outfile=str(parameters.output_path("travel_time.csv")),
    )

    # Run the simulation
    supervisor.run(
        parameters.start_time,
        parameters.end_time,
        parameters.flow_timestep,
        parameters.assignment_factor,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a MnMS simulation.")
    parser.add_argument(
        "config_file",
        nargs="?",
        type=Path,
        help="path to the JSON configuration file",
    )
    arguments = parser.parse_args()
    run_simulation(MnMSParameters(arguments.config_file))

    print("Simulation completed successfully")