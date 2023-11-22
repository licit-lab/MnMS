import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.patches import Patch

from mnms.time import Time


def draw_roads(ax, roads, color='black', linkwidth=1, nodesize=2, node_label=True, draw_stops=True, label_size=5):
    lines = list()

    for section_data in roads.sections.values():
        unode = section_data.upstream
        dnode = section_data.downstream
        lines.append([roads.nodes[unode].position, roads.nodes[dnode].position])
    line_segment = LineCollection(lines, linestyles='solid', colors=color, linewidths=linkwidth)
    ax.add_collection(line_segment)

    x, y = zip(*[rn.position.tolist() for rn in roads.nodes.values()])
    ax.plot(x, y, 'o', markerfacecolor='white', markeredgecolor=color, fillstyle='full', markersize=nodesize)

    if draw_stops and roads.stops:
        x, y = zip(*[stop.absolute_position.tolist() for stop in roads.stops.values()])
        ax.plot(x, y, 'o', markerfacecolor='red', markeredgecolor='red', fillstyle='full', markersize=5)

    if node_label:
        [ax.annotate(n, rn.position, size=label_size) for n, rn in roads.nodes.items()]
        if draw_stops:
            [ax.annotate(s, data.absolute_position, size=label_size, color="red") for s, data in roads.stops.items()]

    ax.margins(0.05, 0.05)
    ax.axis("equal")
    plt.tight_layout()


def draw_path(ax, mlgraph, path, color='red', linkwidth=2, alpha=1):
    lines = list()
    gnodes = mlgraph.graph.nodes
    if path is not None:
        pnodes = path.nodes
        for ni in range(len(pnodes) - 1):
            nj = ni + 1
            unode = gnodes[pnodes[ni]].position
            dnode = gnodes[pnodes[nj]].position
            lines.append([unode, dnode])

        line_segment = LineCollection(lines, linestyles='solid', colors=color, linewidths=linkwidth, alpha=alpha)
        ax.add_collection(line_segment)

def draw_line(ax, mlgraph, line, color='green', linkwidth=6, stopmarkeredgewidth=1, alpha=0.6, draw_stops=True,
    nodesize=6, line_label='', label_size=5):
    lines = list()
    starting_stop = mlgraph.roads.stops[line['stops'][0]]
    ending_stop = mlgraph.roads.stops[line['stops'][-1]]
    for i,sections in enumerate(line['sections']):
        for j,section in enumerate(sections):
            section_data = mlgraph.roads.sections[section]
            unode_pos = mlgraph.roads.nodes[section_data.upstream].position
            dnode_pos = mlgraph.roads.nodes[section_data.downstream].position
            if i == 0 and j == 0:
                # Use strating stop position as unode
                unode_pos = starting_stop.absolute_position
            if i == len(line['sections'])-1 and j == len(sections)-1:
                # Use ending stop position as dnode
                dnode_pos = ending_stop.absolute_position
            lines.append([unode_pos, dnode_pos])
    line_segment = LineCollection(lines, linestyles='solid', colors=color,
        linewidths=linkwidth, alpha=alpha)
    ax.add_collection(line_segment)

    if line_label != '':
        ax.annotate(line_label, starting_stop.absolute_position, size=label_size)

    if draw_stops:
        x, y = zip(*[mlgraph.roads.stops[stop].absolute_position.tolist() for stop in line['stops']])
        ax.plot(x, y, 'o', markerfacecolor=color, markeredgecolor='black',
            fillstyle='full', markersize=nodesize, markeredgewidth=stopmarkeredgewidth)


def draw_odlayer(ax, mlgraph, color='blue', nodesize=2, node_label=True, label_size=5):
    ods = list(mlgraph.odlayer.origins.keys()) + list(mlgraph.odlayer.destinations.keys())
    x, y = zip(*[mlgraph.graph.nodes[od].position for od in ods])
    ax.plot(x, y, 'o', markerfacecolor=color, markeredgecolor='black',
        fillstyle='full', markersize=nodesize)

    if node_label:
        [ax.annotate(od,mlgraph.graph.nodes[od].position, size=label_size) for od in ods]

def draw_veh_activity(ax, veh_result_file: str, veh_id: str):
    c_dict = {'STOP': '#E64646', 'PICKUP': '#E69646', 'SERVING': '#34D05C',
              'REPOSITIONING': '#34D0C3'}
    df = pd.read_csv(veh_result_file, sep=";")
    df = df[df["ID"] == int(veh_id)]
    current_state = df.iloc[0]["STATE"]
    start_time = Time(df.iloc[0]["TIME"])
    current_passengers = df.iloc[0]["PASSENGERS"] if not pd.isna(df.iloc[0]["PASSENGERS"]) else ""
    xticks = []
    i = 0
    for idx, row in df.iterrows():
        next_state = row.STATE
        next_passengers = row.PASSENGERS if not pd.isna(row.PASSENGERS) else ""
        end_time = Time(row.TIME)
        xticks.append(end_time.to_seconds())
        if next_state != current_state:
            ax.barh(f"ACTIVITY_{i}", (end_time - start_time).to_seconds(), left=start_time.to_seconds(), height=0.5,
                    color=c_dict[current_state])
            ax.axvline(x=start_time.to_seconds(), color='k', ls='--')
            ax.text(end_time.to_seconds() + 1, f"ACTIVITY_{i}",
                    next_passengers,
                    va='center', alpha=0.8)
            current_state = next_state
            current_passengers = next_passengers
            start_time = end_time
        elif next_passengers != current_passengers:
            ax.barh(f"ACTIVITY_{i}", (end_time - start_time).to_seconds(), left=start_time.to_seconds(), height=0.5,
                    color=c_dict[current_state])
            ax.axvline(x=start_time.to_seconds(), color='k', ls='--')
            ax.text(end_time.to_seconds() + 1, f"ACTIVITY_{i}",
                    next_passengers,
                    va='center', alpha=0.8)
            current_state = next_state
            start_time = end_time
            current_passengers = next_passengers
        i += 1

    ax.set_xticks(xticks)
    ax.set_xticklabels([Time.from_seconds(x).time for x in xticks])
    plt.xticks(rotation=45)
    plt.tight_layout()
    legend_elements = [Patch(facecolor=c_dict[i], label=i) for i in c_dict]
    plt.legend(handles=legend_elements)
    ax.xaxis.set_major_locator(plt.MaxNLocator(20))
