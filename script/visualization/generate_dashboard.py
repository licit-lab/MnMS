"""
Generate a dashboard of a MnMS network displaying different views
"""

import os
import argparse
import json
import re

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import dash
from dash import dcc, html


# Build adjacency matrix from SECTIONS for network connectivity analysis
def build_adjacency_matrix(network):
    # Create DataFrame of sections
    df_links = pd.DataFrame(network['ROADS']['SECTIONS'].values())

    # Get all unique nodes from upstream and downstream columns
    all_nodes = np.union1d(df_links.upstream.unique(), df_links.downstream.unique())
    df_adj = pd.DataFrame(index=all_nodes, columns=all_nodes)

    # Mark adjacency where sections connect nodes
    for _, row in df_links.iterrows():
        df_adj.loc[row.upstream, row.downstream] = 1

    # Fill missing values with 0 (no connection)
    df_adj.fillna(0, inplace=True)

    return df_adj


# Identify dead-end nodes with no outgoing edges
def identify_deadends(df_adj):
    df_adj_de = df_adj.copy()
    # Find nodes with no outgoing edges
    s_deadEnds = (df_adj_de == 0).all(axis=1)
    ls_deadEnds = s_deadEnds[s_deadEnds].index

    while True:
        # Remove columns corresponding to identified dead ends
        df_adj_de.loc[:, ls_deadEnds] = 0
        s_deadEnds = (df_adj_de == 0).all(axis=1)
        new_deadEnds = s_deadEnds[s_deadEnds].index

        # Stop when no new dead ends found
        if new_deadEnds.equals(ls_deadEnds):
            break
        else:
            ls_deadEnds = new_deadEnds

    ls_deadEnds = new_deadEnds

    return ls_deadEnds


# Identify spring nodes with no incoming edges
def identify_springs(df_adj):
    df_adj_sp = df_adj.copy()
    # Find nodes with no incoming edges
    s_springs = (df_adj_sp == 0).all(axis=0)
    ls_springs = s_springs[s_springs].index

    while True:
        # Remove rows corresponding to identified springs
        df_adj_sp.loc[s_springs, :] = 0
        s_springs = (df_adj_sp == 0).all(axis=0)
        new_springs = s_springs[s_springs].index

        # Stop when no new springs found
        if new_springs.equals(ls_springs):
            break
        else:
            ls_springs = new_springs

    ls_springs = new_springs

    return ls_springs


# Find final sections ending in dead-end nodes
def identify_final_sections(deadends):
    final_sections = []
    sections = roads.get("SECTIONS")

    # Iterate over deadends and find sections ending there
    for deadend in deadends:
        for id, section in sections.items():
            downnode = section["downstream"]
            if deadend == downnode:
                final_sections.append(section["id"])

    return final_sections


# Identify duplicate sections based on upstream/downstream node pairs
def identify_duplicate_sections(sections):
    duplicates = []
    seen_pairs = {}

    for id, section in sections.items():
        id_section = section["id"]
        upnode = section["upstream"]
        downnode = section["downstream"]
        pair = (upnode, downnode)

        # Mark as duplicate if pair already seen
        if pair in seen_pairs:
            duplicates.append(id_section)
        else:
            seen_pairs[pair] = []
        seen_pairs[pair].append(id_section)

    return seen_pairs


# Build adjacency matrix from SECTIONS for network connectivity analysis
def build_adjacency_matrix(network):
    # Create DataFrame of sections
    df_links = pd.DataFrame(network['ROADS']['SECTIONS'].values())

    # Get all unique nodes from upstream and downstream columns
    all_nodes = np.union1d(df_links.upstream.unique(), df_links.downstream.unique())
    df_adj = pd.DataFrame(index=all_nodes, columns=all_nodes)

    # Mark adjacency where sections connect nodes
    for _, row in df_links.iterrows():
        df_adj.loc[row.upstream, row.downstream] = 1

    # Fill missing values with 0 (no connection)
    df_adj = df_adj.fillna(0).infer_objects(copy=False)

    return df_adj


# Compute centrality as number of connected sections per node
def compute_centralities(roads):
    nodes = roads.get("NODES")
    sections = roads.get("SECTIONS")
    centralities = {}

    # Count connections per node
    for id, node in nodes.items():
        id_node = node["id"]
        for id, section in sections.items():
            upnode = section["upstream"]
            downnode = section["downstream"]
            if id_node == upnode:
                centralities[id_node] = centralities.get(id_node, 0) + 1
            if id_node == downnode:
                centralities[id_node] = centralities.get(id_node, 0) + 1

    return centralities


def plot_nodes(roads, springs, deadends, isolates):
    nodes = roads.get("NODES", {})

    set_springs = set(springs)
    set_deadends = set(deadends)
    set_isolates = set(isolates)

    # Prepare categories
    categories = {
        "Isolates": {"color": "black", "ids": set_isolates},
        "Springs": {"color": "green", "ids": set_springs - set_isolates},
        "Deadends": {"color": "red", "ids": set_deadends - set_isolates},
        "Standard": {
            "color": "lightgrey",
            "ids": set(nodes.keys()) - (set_springs | set_deadends | set_isolates),
        },
    }

    fig = go.Figure()

    # Add one trace per category
    for name, info in categories.items():
        ids = info["ids"]
        if not ids:
            continue  # Skip empty categories

        x = [float(nodes[i]["position"][0]) for i in ids if i in nodes]
        y = [float(nodes[i]["position"][1]) for i in ids if i in nodes]

        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode="markers",
            name=name,
            marker=dict(color=info["color"], size=6),
            legendgroup=name,
            showlegend=True,
            hovertext=[f"Node ID: {i}" for i in ids],
            hoverinfo="text",
        ))

    fig.update_layout(
        title="Nodes by Category",
        template="plotly_white",
        width=1500,
        height=1000,
        xaxis=dict(
            tickformat=",d",
            exponentformat="none"
        ),
        yaxis=dict(
            tickformat=",d",
            exponentformat="none"
        ),
        legend=dict(
            title="Node Type",
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="lightgray",
            borderwidth=1,
            x=1.02,
            y=1,
        ),
    )

    fig.update_yaxes(scaleanchor="x", scaleratio=1)

    return fig


def plot_sections(roads):
    nodes = roads.get("NODES", {})
    sections = roads.get("SECTIONS", {})

    # Precompute node coordinates
    node_coords = {
        n["id"]: (float(n["position"][0]), float(n["position"][1]))
        for n in nodes.values()
    }

    fig = go.Figure()

    # Add one line per section for hover clarity
    for sec in sections.values():
        up, down = sec["upstream"], sec["downstream"]
        if up in node_coords and down in node_coords:
            ux, uy = node_coords[up]
            dx, dy = node_coords[down]

            # Custom hover text with HTML formatting
            # Too much information can slow the dashboard
            hovertext = (
                f"<b>ID:</b> {sec['id']}<br>"
                # f"<b>Upstream:</b> {up}<br>"
                # f"<b>Downstream:</b> {down}<br>"
                # f"<b>Length:</b> {sec.get('length', 'N/A')}"
            )

            fig.add_trace(go.Scatter(
                x=[ux, dx],
                y=[uy, dy],
                mode="lines",
                line=dict(color="gray", width=1),
                # hovertext=[hovertext, hovertext],  # same for both points
                # hoverinfo="text",
                showlegend=False,
            ))

    fig.update_layout(
        title="Sections",
        template="plotly_white",
        width=1500,
        height=1000,
        xaxis=dict(
            tickformat=",d",
            exponentformat="none"
        ),
        yaxis=dict(
            tickformat=",d",
            exponentformat="none"
        ),
        hoverlabel=dict(
            bgcolor="white",
            bordercolor="gray",
            font_size=12,
            font_family="Arial"
        )
    )

    fig.update_yaxes(scaleanchor="x", scaleratio=1)

    return fig


def plot_stops(roads):
    stops = roads.get("STOPS", {})
    fig = go.Figure()

    # --- Define color map for known modes ---
    color_map = {
        "BUS": "green",
        "METRO": "red",
        "TRAM": "purple",
    }

    # --- Generic fallback colors for unknown keywords ---
    default_colors = px.colors.qualitative.Plotly
    default_color_index = 0

    # --- Group stops by detected mode ---
    grouped_stops = {}

    for stop_id, stop in stops.items():
        # Extract keyword (first uppercase token, e.g. "BUS" in "BUS_10_DIR1_...")
        match = re.match(r"([A-Z]+)", stop_id)
        mode = match.group(1) if match else "OTHER"

        # Assign a color (predefined or new from default palette)
        if mode not in color_map:
            color_map[mode] = default_colors[default_color_index % len(default_colors)]
            default_color_index += 1

        grouped_stops.setdefault(mode, []).append(stop)

    # --- Plot each mode with its color ---
    for mode, stops_list in grouped_stops.items():
        x = [float(s["absolute_position"][0]) for s in stops_list]
        y = [float(s["absolute_position"][1]) for s in stops_list]

        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode="markers",
            name=mode,
            marker=dict(color=color_map[mode], size=8, opacity=0.8),
            hovertext=[s["id"] for s in stops_list],
            hoverinfo="text"
        ))

    fig.update_layout(
        title="Stops",
        template="plotly_white",
        width=2000,
        height=1000,
        xaxis=dict(
            tickformat=",d",
            exponentformat="none"
        ),
        yaxis=dict(
            tickformat=",d",
            exponentformat="none"
        ),
        legend=dict(
            title="Mode",
            x=1.02,
            y=1,
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="lightgray",
            borderwidth=1
        )
    )

    fig.update_yaxes(scaleanchor="x", scaleratio=1)

    return fig


def plot_centralities(roads, centralities, max_degree):
    nodes = roads.get("NODES", {})
    fig = go.Figure()
    x, y, d = [], [], []

    for nid, val in centralities.items():
        node = nodes[nid]
        x.append(float(node["position"][0]))
        y.append(float(node["position"][1]))
        d.append(val)

    fig.add_trace(go.Scatter(
        x=x, y=y,
        mode="markers",
        marker=dict(size=8, color=d, colorscale="YlOrRd", cmin=0, cmax=max_degree,
                    colorbar=dict(title="Centrality")),
        hovertext=[f"Node ID: {i}" for i in centralities],
        hoverinfo="text",
    ))

    fig.update_layout(
        title="Node Centralities",
        template="plotly_white",
        width=1500,
        height=1000,
        xaxis=dict(
            tickformat=",d",
            exponentformat="none"
        ),
        yaxis=dict(
            tickformat=",d",
            exponentformat="none"
        )
    )

    fig.update_yaxes(scaleanchor="x", scaleratio=1)

    return fig


def plot_pt_lines(roads, layers):
    stops = roads.get("STOPS", {})
    fig = go.Figure()

    # --- Define color by mode ---
    color_map = {
        "BUS": "green",
        "METRO": "red",
        "TRAM": "purple",
    }
    default_colors = px.colors.qualitative.Plotly
    default_color_index = 0

    # --- Collect and group lines by mode ---
    grouped_lines = {}
    for layer in layers:
        if layer.get("TYPE") == "mnms.graph.layers.PublicTransportLayer":
            for line in layer["LINES"]:
                lid = line["ID"]

                # Extract mode keyword from line ID
                match = re.match(r"([A-Z]+)_", lid)
                mode = match.group(1) if match else "OTHER"

                if mode not in color_map:
                    color_map[mode] = default_colors[default_color_index % len(default_colors)]
                    default_color_index += 1

                grouped_lines.setdefault(mode, []).append(line)

    # --- Plot grouped lines ---
    for mode, lines in grouped_lines.items():
        color = color_map[mode]
        first_trace = True  # Only show legend entry once per mode

        for line in lines:
            lid = line["ID"]
            lstops = line["STOPS"]

            xvalues, yvalues = [], []
            for lstop in lstops:
                stop = stops.get(lstop)
                if stop:
                    xvalues.append(float(stop["absolute_position"][0]))
                    yvalues.append(float(stop["absolute_position"][1]))

            if not xvalues:
                continue

            fig.add_trace(go.Scatter(
                x=xvalues,
                y=yvalues,
                mode="lines+markers",
                line=dict(color=color, width=2),
                name=f"{mode if first_trace else lid}",  # Show mode name first, then line ID
                legendgroup=mode,       # Group all same-mode traces
                showlegend=first_trace, # Only one legend item per mode
                hovertext=lid,
                hoverinfo="text"
            ))

            first_trace = False

    # --- Layout ---
    fig.update_layout(
        title="Public Transport Lines",
        template="plotly_white",
        width=2000,
        height=1000,
        xaxis=dict(
            tickformat=",d",
            exponentformat="none"
        ),
        yaxis=dict(
            tickformat=",d",
            exponentformat="none"
        ),
        legend=dict(
            title="Mode",
            x=1.02,
            y=1,
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="lightgray",
            borderwidth=1
        )
    )

    # Keep equal aspect ratio for coordinates
    fig.update_yaxes(scaleanchor="x", scaleratio=1)

    return fig


def plot_zones(roads):
    zones = roads.get("ZONES", {})
    fig = go.Figure()
    cmap = px.colors.qualitative.Set3

    for i, (zid, zone) in enumerate(zones.items()):
        contour = np.array(zone["contour"], dtype=float)
        color = cmap[i % len(cmap)]
        fig.add_trace(go.Scatter(
            x=contour[:, 0],
            y=contour[:, 1],
            mode="lines",
            fill="toself",
            fillcolor=color,
            line=dict(color=color, width=1.5),
            name=f"Zone {zid}",
            opacity=0.4
        ))

    fig.update_layout(
        title="Zones",
        template="plotly_white",
        width=1500,
        height=1000,
        xaxis=dict(
            tickformat=",d",
            exponentformat="none"
        ),
        yaxis=dict(
            tickformat=",d",
            exponentformat="none"
        )
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1)

    return fig


# Dash App
def run_dash_app(roads, layers, springs, deadends, isolates, centralities, max_degree):
    app = dash.Dash(__name__)

    app.layout = html.Div([
        html.H1("MnMS Network Dashboard", style={"textAlign": "center"}),
        dcc.Tabs([
            dcc.Tab(label="Nodes", children=[dcc.Graph(figure=plot_nodes(roads, springs, deadends, isolates))]),
            dcc.Tab(label="Sections", children=[dcc.Graph(figure=plot_sections(roads))]),
            dcc.Tab(label="Stops", children=[dcc.Graph(figure=plot_stops(roads))]),
            dcc.Tab(label="Centralities", children=[dcc.Graph(figure=plot_centralities(roads, centralities, max_degree))]),
            dcc.Tab(label="Public Transport Lines", children=[dcc.Graph(figure=plot_pt_lines(roads, layers))]),
            dcc.Tab(label="Zones", children=[dcc.Graph(figure=plot_zones(roads))]),
        ])
    ])

    app.run(debug=True, port=8050)


# Load the JSON network file from disk
def extract_file(file):
    json_file = open(file)
    network = json.load(json_file)
    json_file.close()

    return network


# Custom argparse type to check if path is valid file
def _path_file_type(path):
    if os.path.isfile(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid path")


# Main script execution starts here
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a MnMS Network Dashboard visualization")
    parser.add_argument('network_file', type=_path_file_type, help='Path to the network JSON file')

    args = parser.parse_args()

    # Extract network data from file
    network = extract_file(args.network_file)

    roads = network.get("ROADS")
    layers = network.get("LAYERS")

    if not roads or not layers:
        print(f'Incorrect json format for {args.network_file}')
        exit()

    df_adj = build_adjacency_matrix(network)

    springs = identify_springs(df_adj)
    deadends = identify_deadends(df_adj)
    isolates = [value for value in deadends if value in springs]

    centralities = compute_centralities(roads)
    max_centrality = max(centralities.values())

    run_dash_app(roads, layers, springs, deadends, isolates, centralities, max_centrality)
