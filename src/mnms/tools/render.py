from itertools import cycle

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
import matplotlib.colors as mcolors

import numpy as np


def draw_flow_graph(ax, G, color='black', linkwidth=1, nodesize=2, node_label=True, show_length=False, cmap=plt.cm.jet):
    lines = list()

    if show_length:
        lengths = list()
        for (unode, dnode), l in G.sections.items():
            lines.append([G.nodes[unode].pos, G.nodes[dnode].pos])
            lengths.append(l.length)
        line_segment = LineCollection(lines, linestyles='solid', array=lengths, linewidths=linkwidth, cmap=cmap)
        ax.add_collection(line_segment)
        plt.colorbar(line_segment)
    else:
        for unode, dnode in G.sections:
            lines.append([G.nodes[unode].pos, G.nodes[dnode].pos])
        line_segment = LineCollection(lines, linestyles='solid', colors=color, linewidths=linkwidth)
        ax.add_collection(line_segment)

    x, y = zip(*[n.pos for n in G.nodes.values()])
    ax.plot(x, y, 'o', markerfacecolor='white', markeredgecolor=color, fillstyle='full', markersize=nodesize)

    if node_label:
        [ax.annotate(n.id, n.pos) for n in G.nodes.values()]

    ax.margins(0.05, 0.05)
    ax.axis("equal")
    plt.tight_layout()


def draw_path(ax, mmgraph, path, color='red', linkwidth=2, alpha=1):
    lines = list()
    if path is not None:
        for ni in range(len(path)-1):
            nj = ni + 1
            unode = mmgraph.mobility_graph.nodes[path[ni]].reference_node
            dnode = mmgraph.mobility_graph.nodes[path[nj]].reference_node
            lines.append([mmgraph.flow_graph.nodes[unode].pos, mmgraph.flow_graph.nodes[dnode].pos])

        line_segment = LineCollection(lines, linestyles='solid', colors=color, linewidths=linkwidth, alpha=alpha)
        ax.add_collection(line_segment)


def draw_multimodal_graph(ax, mmgraph, linkwidth=1, nodesize=5, node_label=True, dy=0.4, defo_scale=0.25):
    flow_graph= mmgraph.flow_graph

    lines = list()
    deformation_matrix = np.array([[1, defo_scale], [0, defo_scale]])
    defo_app = lambda x: deformation_matrix.dot(x)

    for unode, dnode in flow_graph.sections:
        lines.append([defo_app(flow_graph.nodes[unode].pos), defo_app(flow_graph.nodes[dnode].pos)])

    line_segment = LineCollection(lines, linestyles='solid', colors='black', linewidths=linkwidth)
    ax.add_collection(line_segment)
    x, y = zip(*[defo_app(n.pos) for n in flow_graph.nodes.values()])

    ax.plot(x, y, 'o', markerfacecolor='white', markeredgecolor='black', fillstyle='full', markersize=nodesize)

    if node_label:
        [ax.annotate(n.id, defo_app(n.pos)) for n in flow_graph.nodes.values()]

    ax.margins(0.05, 0.05)
    ax.axis("equal")

    all_color = list(mcolors.BASE_COLORS.keys())
    all_color.remove('w')
    colors = cycle(all_color)
    yshift = dy

    service_shift = dict()
    custom_legend = []
    for sid, service in mmgraph.layers.items():
        c = next(colors)
        custom_legend.append(Line2D([0], [0], color=c, lw=2))
        defo_app = lambda x: deformation_matrix.dot(x) + [0, yshift]
        lines = list()
        nodes = set()
        for (unode, dnode) in service.graph.sections:
            link = mmgraph.mobility_graph.sections[(unode, dnode)]
            nodes.add(unode)
            nodes.add(dnode)
            for lid in link.reference_links:
                unode, dnode = mmgraph.flow_graph._map_lid_nodes[lid]
                lines.append(
                    [defo_app(mmgraph.flow_graph.nodes[unode].pos), defo_app(mmgraph.flow_graph.nodes[dnode].pos)])

        line_segment = LineCollection(lines, linestyles='solid', colors=c, linewidths=linkwidth)
        ax.add_collection(line_segment)

        x, y = zip(*[defo_app(mmgraph.flow_graph.nodes[mmgraph.mobility_graph.nodes[n].reference_node].pos) for n in nodes if mmgraph.mobility_graph.nodes[n].reference_node is not None])
        ax.plot(x, y, 'o', markerfacecolor='white', markeredgecolor=c, fillstyle='full', markersize=nodesize)

        if node_label:
            [ax.annotate(n, defo_app((mmgraph.flow_graph.nodes[mmgraph.mobility_graph.nodes[n].reference_node].pos))) for n in nodes if mmgraph.mobility_graph.nodes[n].reference_node is not None]

        service_shift[sid] = yshift
        yshift += dy

    ax.add_collection(line_segment)
    ax.legend(custom_legend, list(mmgraph.layers.keys()))
    plt.tight_layout()