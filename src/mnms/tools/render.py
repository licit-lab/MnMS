import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.patches import Patch
import numpy as np
import seaborn as sns
from matplotlib.lines import Line2D

from mnms.time import Time


def draw_roads(ax, roads, color='black', linkwidth=1, nodesize=2, node_label=True, draw_stops=True, label_size=5, highlight_section=None):
    lines = list()

    for section_data in roads.sections.values():
        unode = section_data.upstream
        dnode = section_data.downstream
        lines.append([roads.nodes[unode].position, roads.nodes[dnode].position])
        if section_data.id == highlight_section:
            line_highlight = [roads.nodes[unode].position, roads.nodes[dnode].position]
            line_segment_highlight = LineCollection([line_highlight], linestyles='solid', colors='orange', linewidths=linkwidth*3)
            ax.add_collection(line_segment_highlight)
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


def draw_path(ax, mlgraph, path, color='orange', linkwidth=2, alpha=1, nodes=False, markersize=10, label_size=5, colors=None):
    lines = list()
    if colors is not None:
        lines_colors = list()
    gnodes = mlgraph.graph.nodes
    if path is not None:
        pnodes = path.nodes if not nodes else path
        for ni in range(len(pnodes) - 1):
            nj = ni + 1
            unode = gnodes[pnodes[ni]].position
            dnode = gnodes[pnodes[nj]].position
            if colors is not None:
                link_label = gnodes[pnodes[ni]].adj[pnodes[nj]].label
                assert link_label in colors, f'Cannot find color for {link_label}...'
                lines_colors.append(colors[link_label])
            lines.append([unode, dnode])

        if colors is not None:
            line_segment = LineCollection(lines, linestyles='solid', colors=lines_colors, linewidths=linkwidth, alpha=alpha)
        else:
            line_segment = LineCollection(lines, linestyles='solid', colors=color, linewidths=linkwidth, alpha=alpha)
        ax.add_collection(line_segment)

    on_pos = gnodes[path.nodes[0]].position if not nodes else gnodes[path[0]].position
    ax.scatter([on_pos[0]], [on_pos[1]], color='blue', s=markersize, label='Origin')
    dn_pos = gnodes[path.nodes[-1]].position if not nodes else gnodes[path[-1]].position
    ax.scatter([dn_pos[0]], [dn_pos[1]], color='red', s=markersize, label='Destination')

    if colors is not None:
        colors_sel = set(lines_colors)
        legend = [Line2D([0, 1], [0, 1], color=colors[m], linewidth=linkwidth, label=m) for m in colors if colors[m] in colors_sel]
        legend += [Line2D([0], [0], label='Origin', color='blue',  marker='o', markersize=3, linestyle=''),
            Line2D([0], [0], label='Destination', color='red', marker='o', markersize=3, linestyle='')]
        plt.legend(handles=legend)
    else:
        plt.legend()

def draw_paths(ax, mlgraph, paths, color='orange', linkwidth=2, alpha=1, nodes=False, markersize=10, label_size=5, colors=None):
    lines = list()
    oposs = list()
    dposs = list()
    if colors is not None:
        lines_colors = list()
    gnodes = mlgraph.graph.nodes
    for i, path in enumerate(paths):
        if not path:
            continue
        on_pos = np.array(gnodes[path.nodes[0]].position) if not nodes else np.array(gnodes[path[0]].position)
        oposs.append(on_pos)
        dn_pos = np.array(gnodes[path.nodes[-1]].position) if not nodes else np.array(gnodes[path[-1]].position)
        dposs.append(dn_pos)
        pnodes = path.nodes if not nodes else path
        for ni in range(len(pnodes) - 1):
            nj = ni + 1
            unode = gnodes[pnodes[ni]].position
            dnode = gnodes[pnodes[nj]].position
            if colors is not None:
                link_label = gnodes[pnodes[ni]].adj[pnodes[nj]].label
                assert link_label in colors, f'Cannot find color for {link_label}...'
                lines_colors.append(colors[link_label])
            lines.append([unode, dnode])

        if colors is not None:
            line_segment = LineCollection(lines, linestyles='solid', colors=lines_colors, linewidths=linkwidth, alpha=alpha)
        else:
            line_segment = LineCollection(lines, linestyles='solid', colors=color, linewidths=linkwidth, alpha=alpha)
        ax.add_collection(line_segment)

    oposs = np.array(oposs)
    dposs = np.array(dposs)
    ax.scatter(oposs[:,0], oposs[:,1], color='blue', s=markersize, label='Origin')
    ax.scatter([dposs[:,0]], [dposs[:,1]], color='red', s=markersize, label='Destination')

    if colors is not None:
        colors_sel = set(lines_colors)
        legend = [Line2D([0, 1], [0, 1], color=colors[m], linewidth=linkwidth, label=m) for m in colors if colors[m] in colors_sel]
        legend += [Line2D([0], [0], label='Origin', color='blue',  marker='o', markersize=3, linestyle=''),
            Line2D([0], [0], label='Destination', color='red', marker='o', markersize=3, linestyle='')]
        plt.legend(handles=legend)
    else:
        plt.legend()


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


def draw_odlayer(ax, mlgraph, color='blue', nodesize=2, node_label=True, label_size=5, markeredgewidth=1):
    ods = list(mlgraph.odlayer.origins.items()) + list(mlgraph.odlayer.destinations.items())
    for odid, od in ods:
        ax.plot(od[0], od[1], 'o', markerfacecolor=color, markeredgecolor='black', markeredgewidth=markeredgewidth,
            fillstyle='full', markersize=nodesize)

    if node_label:
        [ax.annotate(odid,mlgraph.graph.nodes[odid].position, size=label_size) for odid, od in ods if 'ORIGIN' in odid]

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

def draw_links_load(ax, graph, loads, n, linkwidth=1, lmin=None, lmax=None):
    """Function to represent loads on the links of a graph with a colormap.
    Only the links for which a load is specified are represented.

    Args:
        -ax: matplotlib axes
        -graph: graph the links we want to represent belong to
        -loads: dict with links ids and associated loads.
        -n: granularity of the colormap
    """
    lines = list()
    colors_load = list()
    min_load = min(loads.values())
    gnodes = graph.nodes
    glinks = graph.links
    if lmin is not None:
        min_load = min(lmin, min_load)
    max_load = max(loads.values())
    if lmax is not None:
        max_load = max(lmax, max_load)
    colors = plt.cm.cool(np.linspace(0, 1,n))
    color_step = (max_load - min_load) / (n-1)
    loads_sorted = [(lid,load) for lid,load in loads.items()]
    loads_sorted = sorted(loads_sorted, key=lambda x:x[1])
    for lid, load in loads_sorted:
        assert lid in glinks.keys(), f'Cannot find link {lid} in the graph provided...'
        color_idx = int(divmod(load-min_load, color_step)[0])
        colors_load.append(colors[color_idx])
        unode = glinks[lid].upstream
        dnode = glinks[lid].downstream
        lines.append([gnodes[unode].position, gnodes[dnode].position])
    line_segment = LineCollection(lines, linestyles='solid', colors=colors_load, linewidths=linkwidth)
    ax.add_collection(line_segment)

    ax.margins(0.05, 0.05)
    ax.axis("equal")
    plt.tight_layout()

def draw_sections_load(ax, mlgraph, loads, n, linkwidth=1, lmin=None, lmax=None):
    """Function to represent loads on the sections of roads with a colormap.
    Only the roads for which a load is specified are represented.

    Args:
        -ax: matplotlib axes
        -mlgraph: the multi lauer graph
        -loads: dict with sections ids and associated loads
        -n: granularity of the colormap
    """
    lines = list()
    colors_load = list()
    min_load = min(loads.values())
    gnodes = mlgraph.roads.nodes
    gsections = mlgraph.roads.sections
    if lmin is not None:
        min_load = min(lmin, min_load)
    max_load = max(loads.values())
    if lmax is not None:
        max_load = max(lmax, max_load)
    colors = plt.cm.cool(np.linspace(0, 1,n))
    color_step = (max_load - min_load) / (n-1)
    loads_sorted = [(sid,load) for sid,load in loads.items()]
    loads_sorted = sorted(loads_sorted, key=lambda x:x[1])
    for sid, load in loads_sorted:
        assert sid in gsections.keys(), f'Cannot find section {sid} in the graph provided...'
        color_idx = int(divmod(load-min_load, color_step)[0])
        colors_load.append(colors[color_idx])
        unode = gsections[sid].upstream
        dnode = gsections[sid].downstream
        lines.append([gnodes[unode].position, gnodes[dnode].position])
    line_segment = LineCollection(lines, linestyles='solid', colors=colors_load, linewidths=linkwidth)
    ax.add_collection(line_segment)

    ax.margins(0.05, 0.05)
    ax.axis("equal")
    plt.tight_layout()

def draw_layer(ax, layer, color='black', linkwidth=1, nodesize=2, node_label=True, label_size=5):
    """Method that plots the graph of one layer.

    Args:
        -ax: matplotlib axes
        -layer: the layer which graph should be plotted
        -color: color in which the links should be represented
        -linkwidth: representation width of the links
        -nodesize: representation size of the nodes
        -node_label: annotate the graph if True with nodes IDs
        -label_size: applied if node_label is True
    """
    lines = list()
    lnodes = layer.graph.nodes

    for link_data in layer.graph.links.values():
        unode = link_data.upstream
        dnode = link_data.downstream
        lines.append([lnodes[unode].position, lnodes[dnode].position])
    line_segment = LineCollection(lines, linestyles='solid', colors=color, linewidths=linkwidth)
    ax.add_collection(line_segment)

    x, y = zip(*[n.position for n in lnodes.values()])
    ax.plot(x, y, 'o', markerfacecolor='white', markeredgecolor=color, fillstyle='full', markersize=nodesize)

    if node_label:
        [ax.annotate(nid, n.position, size=label_size) for nid, n in lnodes.items()]

    ax.margins(0.05, 0.05)
    ax.axis("equal")
    plt.tight_layout()

def draw_reservoirs(ax, roads, linkwidth=1, colors=None, label_size=3):
    """Function to represent the reservoirs of a RoadDescriptor object.

    Args:
        -ax: matplotlib axes
        -roads: the RoadDescriptor object
        -linkwidth: width of the link represented
        -colors: as many different colors as the number of reservoirs
        -label_size: size of reservoir IDs labels
    """
    nb_res = len(roads.zones)
    if colors is None:
        if nb_res <= 10:
            colors = sns.color_palette(n_colors=nb_res)
        else:
            raise ValueError('Cannot generate more than 10 different colors automatically, provide a color list...')
    else:
        assert len(colors) == nb_res, f'Provide the same number of colors than the number of reservoirs ({len(roads.zone)})'

    for i,(resid,res) in enumerate(roads.zones.items()):
        lines = list()
        color = colors[i]
        res_sections = [s for sid,s in roads.sections.items() if sid in res.sections]
        for section_data in res_sections:
            unode = section_data.upstream
            dnode = section_data.downstream
            lines.append([roads.nodes[unode].position, roads.nodes[dnode].position])
        line_segment = LineCollection(lines, linestyles='solid', colors=color, linewidths=linkwidth)
        ax.add_collection(line_segment)

    for i, (zid, z) in enumerate(roads.zones.items()):
        t = ax.annotate(zid,z.centroid(), size=label_size, color=colors[i])
        t.set_bbox(dict(facecolor='white', alpha=1, edgecolor=colors[i]))

    ax.margins(0.05, 0.05)
    ax.axis("equal")
    plt.tight_layout()
