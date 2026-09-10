# MNMS NETWORK VIZUALISATION

This repository contains Python scripts and jupyter notebooks for visualizing MnMS mobility network file and animate simulation results

---
# Scripts

## generate_html_map

This Python script loads an MnMS network file in JSON format generated from real data and visualises it using Folium.
It converts the source system coordinates to WGS84 and displays sections and public transport (lines and stops) on a saved interactive HTML map.

<figure align="center">
  <img src="../../docs/images/Lyon_network.png" width="500">
  <figcaption>Example of the rendering of the MnMS network in Lyon</figcaption>
</figure>

### Installation

This Python script can be run outside the conda MnMS environment.

Install missing dependencies with:

````bash
pip install folium
````

````bash
pip install pyproj
````

#### Arguments

- `network_file` – Path to the MnMS network JSON file
- `CRS_src` – EPSG code of coordinate system of the network (EPSG:2154 for RGF93 v1 / Lambert-93 -- France for example)

#### Usage example

````bash
python generate_html_map.py ./mnms_lyon_network.json EPSG:2154
````
---

## generate_dashboard

This Python script loads an MnMS network file in JSON format and generates a dashboard for viewing different views of the network.

<figure align="center">
  <img src="../../docs/images/Lyon63V_dashboard.png" width="500">
  <figcaption>Example of the dashboard of a MnMS network</figcaption>
</figure>

### Installation

This Python script can be run outside the conda MnMS environment.

Install missing dependencies with:

````bash
pip install dash
pip install plotly
````

### Arguments
- `network_file` – Path to the MnMS network JSON file.
---

# Notebooks

## pyvis_network_visualization

This notebook loads a mnms network, generates the corresponding pyvis network (https://pyvis.readthedocs.io) and visualizes it.

<figure align="center">
  <img src="../../docs/images/Athens_pyvis_network.png" width="500">
  <figcaption>Example of the pyvis visualization of a MnMS network</figcaption>
</figure>

### Installation

This Jupyter notebook can be run outside the conda MnMS environment.

Install missing dependencies with:

````bash
pip install pyvis
````

# MNMS animation

## mnms_outputs_animation

This Python script animates the simulated vehicles and users and generates an MP4 video

![Demo](../../docs/images/animation.gif)

### Installation

This Python script can be run outside the conda MnMS environment.

````
### Arguments
- `network_file` – Path to the MnMS network JSON file
- `vehicles_file` – Path to the MnMS output csv file of simulated vehicles
- `users_file` – Path to the MnMS output csv file of simulated users
- `--save_mp4` - Specifies whether to save the animation as an MP4 file (false by default)
-----
