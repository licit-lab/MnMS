# Conversion scripts

This repository contains Python scripts for converting various network format to MnMS specific network format.

---

## Bison conversion

This README part on Bison conversion will only cover the bison/conversion_amsterdam_improved.py script.
This script converts BISON (Netherlands) Public Transport (PT) data in XML and CSV format into a MnMS-compatible multilayer JSON graph.
It extracts bus, tram, and metro lines, processes stops, generates PT layers, and saves the resulting graph.

### Features

- Parses Amsterdam Public Transport  network from BISON KV1-format data.
- Extracts stop coordinates and line definitions from XML + CSV files.
- Supports Bus, Metro, and Tram.
- Creates MnMS PublicTransport layers with timetables and default frequencies.
- Outputs a MnMS multilayer graph (JSON) with:
  - Road nodes & sections
  - Stops & lines
  - PT layers (Bus, Tram, Metro)

### Script structure

#### Parameters

The script defines several constants in the header:
- File paths
  - coord_csv_filepath: CSV file with coordinates
  - metro_xml_directory, tram_xml_directory, bus_xml_directory: XML directories for PT definitions
  - Amsterdam BISON specific dataset structure is described in the Notes below
- Default speeds
  - Bus: 13.8 m/s (50 km/h)
  - Metro: 18 m/s (65 km/h)
  - Tram: 15 m/s (54 km/h)
- Frequencies
  - Bus: every 8 min
  - Metro: every 4 min
  - Tram: every 10 min
- Operation hours
  - Start: 05:00:00
  - End: 23:00:00

#### Functions Description

- `extract_amsterdam_stops(xml_dir)` – Parses XML files for one PT type (bus, tram, or metro).
Builds stop sequences, splits them into two directions, and outputs a list of DataFrames with stops.
  - Args: xml_dir: Directory containing XML definitions of lines.
  - Returns: list of DataFrames (LINE_ID, STOP_NAME, STOP_CODE).


- `generate_public_transportation_lines(layer, list_lines, freq, operation_start_time, operation_end_time, prefix_line_name)`– Generates
PT lines on a given MnMS PublicTransportLayer.
  - Args:
    - layer: Target PT layer (Bus, Tram, Metro).
    - list_lines: List of DataFrames for each line.
    - freq: Frequency (Dt object).
    - operation_start_time: Start time of service.
    - operation_end_time: End time of service.
    - prefix_line_name: Prefix string for line IDs.
  - Returns: None.

#### Script Flow

- Parse input arguments:
  - Load MnMS graph file
  - Define output file
- Extract PT lines from XML directories:
  - Bus, Tram, Metro
- Register stops and sections into road descriptor.
- Overwrite zoning with one global zone.
- Create PT layers (Bus, Tram, Metro) with default frequencies.
- Assemble into a MultiLayerGraph.
- Save graph to output file.

### Installation

Install missing dependencies with:

````bash
pip install lxml
````

### Usage example

````bash
python conversion_gtfs.py base_mnms_graph.json amsterdam_graph.json
````

- `mnms_file` – Base MnMS JSON graph file (without PT).
- `output_file` – Destination for the enriched graph with PT. (created by the script if it doesn’t exist yet)

The script will produce as an output, a MnMS JSON graph containing:
- Road network
- Bus, Tram, Metro layers
- Stops, sections, and PT lines with timetables.

### Notes

As a reminder, only the bison/conversion_amsterdam_improved.py script is described here.

- Amsterdam BISON dataset need to have the following structure:

````bash
KV1_GVB_2609_2/
├── Csv/POINT.csv        # Coordinates of stops
└── Xml/
    ├── BUS/             # Bus operation patterns
    ├── TRAM/            # Tram operation patterns
    └── METRO/           # Metro operation patterns
````

---

## GTFS conversion

This Python script converts GTFS (General Transit Feed Specification) public transport data into an MnMS-compatible JSON network file.

### Features

- Parses GTFS .zip archives as input.
- Uses an existing MnMS road network JSON file as the base.
- Generates an MnMS JSON network representation of the public transport network.

### Script structure

- `cleanString(input_string: str) -> str` – Cleans and normalizes input strings by removing problematic characters (e.g., spaces, special symbols).
This ensures stop names and line identifiers are safe for processing and storage.


- `secondsToMnMsTime(seconds: int) -> str` – Converts time expressed in seconds since midnight into MnMS time format (HH:MM:SS).
Used when adapting GTFS times to MnMS simulation requirements.


- `generate_nx_graph(roads: dict) -> networkx.Graph` – Builds a NetworkX graph representation of the road network from MnMS JSON data.
Each node corresponds to a road node, and each edge represents a road section.


- `closest_node(x: float, y: float, G: networkx.Graph) -> str` – Finds the closest graph node in G to the given coordinates (x, y).
Used for assigning GTFS stops to road network nodes.


- `closest_edge(x: float, y: float, G: networkx.Graph) -> str` – Finds the closest edge (road section) in G to the given coordinates (x, y).
Useful for mapping stops to sections when no node is nearby.


- `getLongestTripStops(trips: dict, stop_times: dict) -> list` – From the GTFS dataset, extracts the longest trip (in terms of number of stops) for each line.
This ensures that the main representative route is used when constructing MnMS lines.


- `gps_inside_box(x: float, y: float, bbox: list) -> bool` – Checks whether the coordinates (x, y) lie inside a given bounding box.
Used to filter out stops that fall outside the target network area.


- `filter_line(line: dict, bbox: list) -> dict` – Filters a GTFS line so that only stops inside the bounding box are kept.
This ensures only relevant transit data is processed.


- `extract_gtfs_stops(gtfs_zip: str) -> dict` – Reads a GTFS archive (.zip) and extracts all stops, mapping them to their coordinates.
Stops are later mapped to MnMS network nodes/sections.


- `generate_public_transportation_lines(gtfs_data: dict, roads: dict) -> dict` – Generates MnMS public transportation lines (routes and stops) from GTFS data.
This provides a first raw conversion into MnMS-compatible structures.


- `generate_map_matching_pt_lines(gtfs_data: dict, G: networkx.Graph, roads: dict) -> dict` – Improves the public transportation lines by performing map matching of stops to the road graph G.
Ensures that generated lines align properly with the MnMS road network.


- `register_pt_lines(roads: dict, pt_lines: dict) -> dict` – Registers the generated public transport lines into the MnMS network JSON.
Updates the ROADS section with PT-specific data.


- `register_map_match_pt_lines(roads: dict, matched_lines: dict) -> dict` – Registers the map-matched PT lines into the MnMS network JSON.
This overwrites/updates existing PT definitions with more accurate ones.


### Installation

Install missing dependencies with:

````bash
pip install gtfs_functions
````

### Usage example

````bash
python conversion_gtfs.py lyon_gtfs.zip lyon_roads.json lyon_gtfs.json
````

- `gtfs_file` – Path to the MnMS network JSON file.
- `mnms_roads_file` – Path to the MnMS network JSON file.
- `mnms_output_file` – Path to the new MnMS network file (created by the script if it doesn’t exist yet)

### Notes

- The GTFS ZIP file must follow standard GTFS format (stops.txt, routes.txt, trips.txt, etc.).
- The script assumes the road network file is already in MnMS JSON format.


---

## NetworkX conversion

This script converts an MnMS network JSON file into a NetworkX MultiDiGraph JSON file.
It enables users and developers to leverage the NetworkX library for advanced graph analysis and visualization.

### Features

- Load MnMS graph using mnms.io.graph.load_graph.
- Extract nodes and sections.
- Convert to a NetworkX MultiDiGraph.
- Serialize to JSON node-link format.
- Save to an output file.

### Script structure

- `generate_nx_graph(nodes, sections) -> nx.MultiDiGraph` – Converts MnMS graph data (nodes and sections) into a NetworkX MultiDiGraph:
  - Adds nodes with positional attributes (x, y).
  - Adds directed edges representing road sections with id and length.

### Installation

Install missing dependencies with:

````bash
pip install networkx
````

### Usage example

````bash
python conversion_nx.py mnms_network.json output/networkx_graph.json
````

- `network_file` – Path to the input MnMS network JSON file. Must exist.
- `networkx_output_file` – Path to the new NetworkX JSON file. Directory must exist, file can be new.

The script will produce as an output, a JSON file containing the NetworkX graph in node-link format.

Example NetworkX structure:

````json
{
  "directed": true,
  "multigraph": true,
  "nodes": [
    {"id": "N1", "position": [0.0, 0.0]},
    {"id": "N2", "position": [10.0, 5.0]}
  ],
  "links": [
    {"source": "N1", "target": "N2", "id": "S1", "length": 100.0}
  ]
}
````

### Notes

---

## OpenStreetMap conversion

This script converts OpenStreetMap (OSM) data into an MnMS-compatible JSON multilayer graph.
It allows researchers and developers to generate MnMS road networks directly from OSM queries such as "Lyon, France".

### Features

- Query OpenStreetMap using osmnx.
- Extract nodes and edges.
- Convert coordinates (WGS → UTM).
- Build MnMS RoadDescriptor with nodes and sections.
- Define zones (single or multiple).
- Create MnMS CarLayer with nodes and links.
- Build the MultiLayerGraph.
- Save to JSON file.

### Script structure

- `convert_osm_to_mnms(osm_query, output_file, zone_dict=None, car_only=False, mono_res=None)` – Main function to convert
an OSM place query into an MnMS-compatible JSON multilayer graph :
  - Loads road network from OSM.
  - Converts WGS coordinates to UTM.
  - Registers nodes and road sections in the MnMS RoadDescriptor.
  - Defines zones either from a bounding box (--mono_res) or a mapping file (--multi_res).
  - Creates the car layer and builds the multilayer graph.
  - Saves result to an output file.

### Installation

Install missing dependencies with:

````bash
pip install osmnx
````

### Usage example

````bash
python conversion_osm.py "Lyon, France" mnms_lyon_osm.json --mono_res ZONE_1
````

- `query` – The OSM place query (string). Example: "Lyon, France".
- `--output_dir` – Path to the output directory (default: current working directory). Must exist.
- `--mono_res` – Define a single reservoir (zone) with the given identifier.
- `--multi_res` – Path to a JSON file mapping sections → reservoirs for multiple zones. Mutually exclusive with --mono_res.

### Notes

The format used for OSM query in example is `City, Country`, OSM queries can be more specific,
please look for OpenStreetMap documentation for custom queries.

---

## Symuflow conversion

This script converts a SymuFlow XML input file into a MnMS-compatible multilayer JSON graph.
It extracts road sections, junctions, stops, and optionally public transport lines,
then builds a MultiLayerGraph including CAR and PT (Public Transport) layers.

### Features

- Parses SymuFlow XML input files.
- Extracts:
  - Road nodes & sections
  - Lanes, reserved lanes, and car accessibility
  - Junctions with allowed/forbidden movements
  - Stops and PT lines (Bus, Tram, Metro)
- Supports car-only mode or multimodal mode (Car + PT).
- Creates a MnMS multilayer graph and saves it as JSON.

### Script structure

#### Functions Description

`convert_symuflow_to_mnms(file, output_dir, zone_dict=None, car_only=False, mono_res=None)`

Main function performing the conversion:
 - Parses XML with lxml.
 - Extracts nodes, road sections, junctions, car accessibility.
 - Computes section lengths from coordinates.
 - Registers zones (single bounding box or multiple from file).
 - Registers stops along sections.
 - Builds:
   - CarLayer with nodes, links, and junction movements.
   - PublicTransportLayer(s) for Bus/Tram/Metro if car_only is False.
 - Generates PT lines with timetables (frequencies or explicit schedules).
 - Assembles layers into a MultiLayerGraph.
 - Saves the graph to JSON.

#### Script Flow

- Parse CLI arguments.
- Parse XML:
  - Road sections (TRONCONS)
  - Junctions (CARREFOURSAFEUX, REPARTITEURS, GIRATOIRES)
  - Stops (ARRETS)
  - Public transport lines (LIGNES_TRANSPORT_GUIDEES)
- Build RoadDescriptor with nodes, sections, stops.
- Create CarLayer with allowed movements and links.
- (Optional) Create PT layers (Bus/Tram/Metro) with timetables.
- Assemble into MultiLayerGraph.
- Save graph as JSON in output_dir.

### Installation

Install missing dependencies with:

````bash
pip install lxml
````

### Usage examples

- Convert with only the car layer:

````bash
python symuflow_conversion.py network.xml --car_only --output_dir ./graphs
````

- Convert with public transport layers and single zone:

````bash
python symuflow_conversion.py network.xml --mono_res RES1 --output_dir ./graphs
````

- Convert with zone mapping:

````bash
python symuflow_conversion.py network.xml --multi_res zones.json --output_dir ./graphs
````

- Arguments

  - `symuflow_graph.xml` – Input SymuFlow XML file.
  - `--output_dir` – Directory where the MnMS JSON graph will be saved (default: current directory).
  - `--car_only` – If set, only the car network is converted (no PT layers).
  - `--mono_res` – Define a single reservoir zone (by ID).
  - `--multi_res` – Path to a JSON mapping sections → reservoirs.


- The script will produce as an output, a MnMS JSON graph containing:

  - Car network (nodes, sections, junctions).
  - Optionally, PT layers (Bus, Tram, Metro).
  - Zones (mono or multi).
  - Stops and PT lines with timetables.

### Notes
