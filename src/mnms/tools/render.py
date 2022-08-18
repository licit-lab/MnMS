import matplotlib.pyplot as plt

from matplotlib.collections import LineCollection


def draw_roads(ax, roads, color='black', linkwidth=1, nodesize=2, node_label=True, draw_stops=True, label_size=5):
    lines = list()

    for section_data in roads.sections.values():
        unode = section_data['upstream']
        dnode = section_data['downstream']
        lines.append([roads.nodes[unode], roads.nodes[dnode]])
    line_segment = LineCollection(lines, linestyles='solid', colors=color, linewidths=linkwidth)
    ax.add_collection(line_segment)

    x, y = zip(*[pos.tolist() for pos in roads.nodes.values()])
    ax.plot(x, y, 'o', markerfacecolor='white', markeredgecolor=color, fillstyle='full', markersize=nodesize)

    if draw_stops:
        x, y = zip(*[data["absolute_position"].tolist() for data in roads.stops.values()])
        ax.plot(x, y, 'o', markerfacecolor='red', markeredgecolor=color, fillstyle='full', markersize=nodesize)


    if node_label:
        [ax.annotate(n, pos, size=label_size) for n, pos in roads.nodes.items()]
        if draw_stops:
            [ax.annotate(n, data['absolute_position'], size=label_size, color="red") for n, data in roads.stops.items()]

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
