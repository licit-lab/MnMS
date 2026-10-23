# Running an MnMS simulation

The `run.py` script reads a JSON configuration, builds the multimodal network,
demand, flow model, and travel decision model, then runs an MnMS simulation for
the configured time period. Simulation results and logs are saved to the
configured output directory.

## Run

From the repository root:

```shell
python script/running/run.py script/running/mnms_settings.json
```

Or from this directory:

```shell
python run.py mnms_settings.json
```

## Configuration and input data

`mnms_settings.json` is ready-to-use example
configurations. They refer to input data in `examples/Lyon63V/INPUTS/`.
Input paths and the output path are resolved relative to the directory
containing the JSON configuration file.

The JSON configuration contains these sections:

- `GRAPH`: network file, origin-destination layer and connection distance,
  mobility services, and connections between layers.
- `DEMAND`: CSV file containing the demand to load.
- `FLOW_MOTOR`: MFD parameters for each reservoir and layer. Each accumulation
  range specifies `min`, `max` (or `"inf"`), `slope`, and `intercept`; speed is
  calculated as `slope × accumulation + intercept`.
- `DECISION_MODEL`: decision model (`logit` or `dummy`) and the number of
  shortest paths to consider.
- `SCENARIO`: start and end times, flow timestep in seconds, assignment factor,
  output directory, and log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, or
  `CRITICAL`).

To use different data, update the paths in the JSON and ensure the referenced
files exist. Configured layers and mobility service types must match the
network. Each road reservoir must also have MFD parameters for its layers.
