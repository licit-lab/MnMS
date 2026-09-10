# Validation scripts

This repository contains Python scripts for validating MnMS input files.

---

## Demand file

This Python script validate a demand input CSV file for MnMS.
The script validates the structure and contents of the demand file, analyzes demand data,
and optionally produces visualizations of origins, destinations, and demand dynamics.

### Features

- **Validation**
  - Ensures CSV has no empty lines.
  - Checks for required columns (`ID`, `DEPARTURE`, `ORIGIN`, `DESTINATION`).
  - Validates:
    - User IDs
    - Departure times (`%H:%M:%S` format)
    - Origin and destination coordinates
    - Journey meaningfulness (origin ≠ destination, distance > radius)
    - Mobility services (if defined)
  - Detects duplicate user IDs.
  - Reports invalid and warning users.


- **Analysis**
  - Prints first and last departure times.
  - Counts users with at least one mandatory mobility service.
  - Reports frequency of each mobility service.


- **Visualization (optional)**
  - Origin coordinates density plot.
  - Destination coordinates density plot.
  - Temporal evolution of demand (users per second).

### Script structure

- **Validation functions**
  - `validate_demand_lines(file)` – Ensures no empty rows in CSV.
  - `validate_demand_columns(df_users)` – Checks required columns.
  - `validate_user_id(user)` – Confirms presence/type of user ID.
  - `validate_user_departure_time(user)` – Validates departure time format.
  - `validate_user_origin(user)` / `validate_user_destination(user)` – Validate coordinates.
  - `validate_user_journey(user, radius)` – Ensures meaningful journey.
  - `validate_user_mobility_services(user)` – Checks for blank mobility services.
  - `check_user_id_duplicates(df_users)` – Finds duplicate user IDs.


- **Analysis functions**
  - `count_ms_occurences(df_users)` – Frequency of mobility services.
  - `analyze_demand(df_users)` – Prints demand statistics.


- **Visualization functions**
  - `scatter_density(fig, x, y, title)` – Density plot helper.
  - `visualize_demand(df_users)` – Plots origin density, destination density, and demand dynamics.

### Usage example

````bash
python validate_demand.py demand.csv --radius 10 --visualization True
````

- `demand_file` – Path to the demand CSV file (semicolon-separated).
- `--radius` – Minimum distance tolerance between origin and destination (default: 0).
- `--visualize` – Whether to plot demand visualizations (True or False).

Considering this csv sample file:

````csv
ID;DEPARTURE;ORIGIN;DESTINATION;MOBILITY SERVICES
1;08:00:00;10.0 20.0;30.0 40.0;Bus
2;08:15:00;15.0 25.0;15.0 25.0;Metro
3;08:30:00;12.0 22.0;32.0 42.0;Bus Metro
4;08:45:00;13.0 23.0;33.0 43.0;
````

The script will produce this output:

````
Warning: origin equals destination for user 2, origin = destination = 15.0 25.0
Total number of users: 4
Number of invalid users: 0
Number of warning users: 1
Validation : 100.0%
First user departure time: 08:00:00
Last user departure time: 08:45:00
Number of users with at least one mandatory mobility service : 3
Mandatory mobility services and occurences: {'Bus': 2, 'Metro': 2}
````

---

## Network file

This Python script validates an MnMS network input JSON file.
The script provides statistics, connectivity analysis,
and optional visualizations of the road network and public transport layers.

### Features

- **Validation**
  - Checks presence of mandatory tags: `NODES`, `STOPS`, `SECTIONS`, `ZONES` in the `ROADS` block.


- **Analysis**
  - Counts nodes, stops, sections, and zones.
  - Reports section statistics (min, max, mean, median length).
  - Computes connectivity index.
  - Identifies:
    - Dead-end nodes
    - Spring nodes
    - Isolates (nodes with no incoming or outgoing edges)
    - Final sections
    - Duplicate sections
  - Computes node centralities (degree of connectivity).


- **Public Transport Analysis**
  - Inspects bus lines in `LAYERS`.
  - Computes map-matching rates of bus line sections.
  - Reports fully/partially map-matched lines.


**Visualization** (optional, requires `--visualize True`)
  - Plots nodes, stops, sections, and zones.
  - Highlights node centralities with color intensity.
  - Visualizes public transport lines.

### Script structure

- **Validation functions**
  - `validate_roads_tag(roads)` – Checks that the `ROADS` object contains the required subtags: `NODES`, `STOPS`, `SECTIONS`, `ZONES`.
  - `validate_layers_tag(layers)` – Placeholder function for validating the `LAYERS` tag (currently does nothing).
  - `validate_roads(roads)` – Validates the `ROADS` tag and prints whether the network is valid.
  - `validate_layers(layers)` – Validates the `LAYERS` tag and prints whether it is valid.


- **Graph and connectivity functions**
  - `build_adjacency_matrix(network)` – Builds an adjacency matrix from the `SECTIONS` to analyze network connectivity.
  - `identify_deadends(df_adj)` – Finds nodes with no outgoing edges (dead-end nodes).
  - `identify_springs(df_adj)` – Finds nodes with no incoming edges (spring nodes).
  - `identify_final_sections(deadends)` – Identifies final sections that end at dead-end nodes.
  - `identify_duplicate_sections(sections)` – Detects duplicate sections with identical upstream–downstream node pairs.
  - `compute_centralities(roads)` – Computes centrality of each node based on the number of connected sections.


- **Analysis functions**
  - `analyze_roads(roads)` – Performs statistical analysis of the road network:
    - Number of nodes, stops, sections, zones
    - Section length statistics (min, max, mean, median)
    - Connectivity index
    - Dead-ends, springs, isolates, final and duplicate sections
  - `analyze_bus(layers)` – Analyzes bus lines in the `LAYERS` tag:
    - Counts bus lines
    - Computes mapmatching rate
    - Identifies fully or partially map-matched lines


- **Visualization functions**
  - `visualize_nodes(roads)` – Scatter plot of all nodes.
  - `visualize_stops(roads)` – Scatter plot of all stops.
  - `visualize_sections(roads)` – Draws sections as lines connecting upstream and downstream nodes.
  - `visualize_zones(roads)` – Plots polygons representing zones from their contours.
  - `visualize_centralities(roads, centralities, max_degree)` – Scatter plot of nodes colored by centrality degree.
  - `visualize_pt_lines(roads, layers)` – Plots public transport lines and their associated stops.

### Usage example

````bash
python validate_network.py mnms_network.json --visualization True
````

- `network_file` – Path to the MnMS network JSON file.
- `--visualize` (optional) – Enable visualizations (default: False).

The script will produce as an output:

- Prints validation and analysis results to the console.
- If visualization is enabled, displays matplotlib figures for:
  - Nodes
  - Stops
  - Sections
  - Zones
  - Public transport lines

### Notes

The `LAYERS` validation is a placeholder for now.
Some advanced analyses (e.g., centrality visualization) are implemented but commented out.
You can enable them as needed.

Ensure your JSON file follows MnMS schema conventions with these top-level tags:

````json
{
  "ROADS": {
    "NODES": { ... },
    "STOPS": { ... },
    "SECTIONS": { ... },
    "ZONES": { ... }
  },
  "LAYERS": [
    {
      "ID": "BUSLayer",
      "TYPE": "mnms.graph.layers.PublicTransportLayer",
      "VEH_TYPE": "BUS",
      "LINES": [ ... ]
    }
  ]
}
````

---

## Transit link file

This Python script validate, analyze and visualize a transit link input JSON file for MnMS.
The script provides summary statistics of transit link lengths and an optional visualization overlaying links on the road network.

### Features

- **Validation**
  - Placeholder for transit link validation (to be implemented later).


- **Analysis**
  - Counts the number of transit links.
  - Computes:
    - Minimum link length
    - Maximum link length
    - Mean link length
    - Median link length


- **Visualization**
  - Plots the entire road network as a background.
  - Overlays transit links in red.
  - Handles both normal nodes and special nodes (`ORIGIN`, `DESTINATION`).

### Script structure

- `validate_transit_links()` – Placeholder function for validating transit links. Currently not implemented.
- `analyze_transit_links(tlinks)` – Analyzes transit links and prints statistics on their lengths (count, min, max, mean, median).
- `visualize_transit_links(tlinks, roads, origins, destinations)` – Plots transit links over the road network:
    - Road nodes in grey.
    - Transit links in red.
    - Supports upstream/downstream connections to ORIGIN or DESTINATION nodes.
- `extract_file(file)` – Reads and parses a JSON file into a Python object.
- `_path_file_type(path)` – Custom `argparse` type to validate that the provided path is an existing file.


### Usage example

````bash
python validate_transit_link.py transit_links.json network.json odlayer.json --visualization True
````

- `transit_link_file` – Path to the transit links JSON file.
- `network_file` – Path to the road network JSON file.
- `odlayer_file` – Path to the OD layer JSON file.
- `--visualize` (optional) – If True, displays a plot of the transit links. (default: False)

### Notes
- `validate_transit_links()` still to be fully implemented
