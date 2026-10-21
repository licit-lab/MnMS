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
                raise ValueError(
                    f"Missing or invalid '{section_name}' section in {self.config_file}"
                )
            setattr(self, section_name.lower(), section)

    def _resolve_path(self, base_directory: str, configured_path: str) -> Path:
        path = Path(configured_path.lstrip("/\\"))
        return (self.config_file.parent / base_directory / path).resolve()

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

def run_simulation(parameters: MnMSParameters) -> None:

    parameters.output_directory.mkdir(parents=True, exist_ok=True)
    set_mnms_logger_level(parameters.log_level, ["mnms.simulation"])
    attach_log_file(str(parameters.output_path(parameters.output["log_file"])))

    network_path = parameters.input_path(parameters.graph["file"])
    mmgraph = load_graph(str(network_path))

    
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
    