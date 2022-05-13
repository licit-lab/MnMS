from mnms.graph.core import MultiModalGraph


def manhattan(n, link_length):
    mmgraph = MultiModalGraph()
    fgraph = mmgraph.flow_graph

    for i in range(n):
        for j in range(n):
            fgraph.create_node(str(i * n + j), [i*link_length, j*link_length])

    for i in range(n):
        for j in range(n):
            ind = i * n + j
            if j < n - 1:
                fgraph.create_link(f"{ind}_{ind + 1}", str(ind), str(ind + 1), link_length)
            if j > 0:
                fgraph.create_link(f"{ind}_{ind - 1}", str(ind), str(ind - 1), link_length)
            if i < n - 1:
                fgraph.create_link(f"{ind}_{ind + n}", str(ind), str(ind + n), link_length)
            if i > 0:
                fgraph.create_link(f"{ind}_{ind - n}", str(ind), str(ind - n), link_length)

    # WEST
    for i in range(n):
        fgraph.create_node(f"WEST_{i}", [-link_length, i*link_length])
        up = f"WEST_{i}"
        down = str(i)
        fgraph.create_link(f"{up}_{down}", up, down, link_length)
        fgraph.create_link(f"{down}_{up}", down, up, link_length)

    # EAST
    for counter, i in enumerate(range(n*(n-1), n*n)):
        up = f"EAST_{counter}"
        down = str(i)
        fgraph.create_node(up, [n*link_length, counter*link_length])
        fgraph.create_link(f"{up}_{down}", up, down, link_length)
        fgraph.create_link(f"{down}_{up}", down, up, link_length)

    # NORTH
    for counter, i in enumerate(range(n-1, n*n, n)):
        up = f"NORTH_{counter}"
        down = str(i)
        fgraph.create_node(up, [counter*link_length, n*link_length])
        fgraph.create_link(f"{up}_{down}", up, down, link_length)
        fgraph.create_link(f"{down}_{up}", down, up, link_length)

    # SOUTH
    for counter, i in enumerate(range(0, n*n, n)):
        up = f"SOUTH_{counter}"
        down = str(i)
        fgraph.create_node(up, [counter*link_length, -link_length])
        fgraph.create_link(f"{up}_{down}", up, down, link_length)
        fgraph.create_link(f"{down}_{up}", down, up, link_length)

    return mmgraph


if __name__ == "__main__":
    from mnms.tools.render import draw_flow_graph
    import matplotlib.pyplot as plt

    mmgraph = manhattan(20, 10)
    #
    fig, ax = plt.subplots()
    draw_flow_graph(ax, mmgraph.flow_graph)
    plt.show()
