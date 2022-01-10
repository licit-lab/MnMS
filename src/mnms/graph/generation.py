from mnms.graph.core import MultiModalGraph



def create_grid_graph(nx, ny, dist=1):
    """ Return a `MultiModalGraph` with a grid like flow graph

    Parameters
    ----------
    nx: int
        number of nodes in the x direction
    ny: int
        number of nodes in the y direction
    dist: float
        distance between two nodes
    Returns
    -------

    """
    mmgraph = MultiModalGraph()
    fgraph = mmgraph.flow_graph

    for i in range(nx):
        for j in range(ny):
            fgraph.add_node(f"{i}{j}", [i*dist, j*dist])

    for i in range(1, nx-1):
        for j in range(1, ny-1):
            upid = f"{i}{j}"
            did = f"{i}{j-1}"
            fgraph.add_link(f"{upid}_{did}", upid, did)
            did = f"{i-1}{j}"
            fgraph.add_link(f"{upid}_{did}", upid, did)
            did = f"{i+1}{j}"
            fgraph.add_link(f"{upid}_{did}", upid, did)
            did = f"{i}{j+1}"
            fgraph.add_link(f"{upid}_{did}", upid, did)

    for i in range(nx-1):
        j = i+1
        uid = f"{i}0"
        did = f"{j}0"
        fgraph.add_link(f"{uid}_{did}", uid, did)
        fgraph.add_link(f"{did}_{uid}", did, uid)

        ext_node = f'S{i}'
        fgraph.add_node(ext_node, [i*dist, -dist])
        fgraph.add_link(f"{ext_node}_{uid}", ext_node, uid)
        fgraph.add_link(f"{uid}_{ext_node}", uid, ext_node)

        uid = f"{i}{ny-1}"
        did = f"{j}{ny-1}"
        # print(uid, did)
        fgraph.add_link(f"{uid}_{did}", uid, did)
        fgraph.add_link(f"{did}_{uid}", did, uid)

        ext_node = f'N{i}'
        fgraph.add_node(ext_node, [i*dist, ny*dist])
        fgraph.add_link(f"{ext_node}_{uid}", ext_node, uid)
        fgraph.add_link(f"{uid}_{ext_node}", uid, ext_node)

    uid = f"{nx-1}0"
    ext_node = f'S{nx-1}'
    fgraph.add_node(ext_node, [(nx-1)*dist, -dist])
    fgraph.add_link(f"{ext_node}_{uid}", ext_node, uid)
    fgraph.add_link(f"{uid}_{ext_node}", uid, ext_node)

    uid = f"{nx-1}{ny-1}"
    ext_node = f'N{nx-1}'
    fgraph.add_node(ext_node, [(nx-1)*dist, ny*dist])
    fgraph.add_link(f"{ext_node}_{uid}", ext_node, uid)
    fgraph.add_link(f"{uid}_{ext_node}", uid, ext_node)

    for i in range(ny-1):
        j = i+1
        uid = f"0{i}"
        did = f"0{j}"
        fgraph.add_link(f"{uid}_{did}", uid, did)
        fgraph.add_link(f"{did}_{uid}", did, uid)

        ext_node = f'W{i}'
        # print(uid, did)
        fgraph.add_node(ext_node, [-1*dist, i*dist])
        fgraph.add_link(f"{ext_node}_{uid}", ext_node, uid)
        fgraph.add_link(f"{uid}_{ext_node}", uid, ext_node)

        uid = f"{nx-1}{i}"
        did = f"{nx-1}{j}"
        # print(uid, did)
        fgraph.add_link(f"{uid}_{did}", uid, did)
        fgraph.add_link(f"{did}_{uid}", did, uid)

        ext_node = f'E{i}'
        fgraph.add_node(ext_node, [nx*dist, i*dist])
        fgraph.add_link(f"{ext_node}_{uid}", ext_node, uid)
        fgraph.add_link(f"{uid}_{ext_node}", uid, ext_node)

    uid = f"0{ny - 1}"
    ext_node = f'W{ny-1}'
    fgraph.add_node(ext_node, [-1*dist, (ny-1)*dist])
    fgraph.add_link(f"{ext_node}_{uid}", ext_node, uid)
    fgraph.add_link(f"{uid}_{ext_node}", uid, ext_node)

    uid = f"{nx-1}{ny - 1}"
    ext_node = f'E{ny-1}'
    fgraph.add_node(ext_node, [nx*dist, (ny-1)*dist])
    fgraph.add_link(f"{ext_node}_{uid}", ext_node, uid)
    fgraph.add_link(f"{uid}_{ext_node}", uid, ext_node)

    if ny > 4:
        for i in range(1, ny - 1):
            uid = f"0{i}"
            did = f"{i+1}{i}"
            fgraph.add_link(f"{uid}_{did}", uid, did)

            uid = f"{nx-1}{i}"
            did = f"{nx-2}{i}"
            fgraph.add_link(f"{uid}_{did}", uid, did)

    if nx > 4:
        for i in range(1, nx - 1):
            uid = f"{i}0"
            did = f"{i}1"
            fgraph.add_link(f"{uid}_{did}", uid, did)

            uid = f"{i}{ny-1}"
            did = f"{i}{ny-2}"
            fgraph.add_link(f"{uid}_{did}", uid, did)

    return mmgraph

if __name__ == "__main__":
    from mnms.tools.render import draw_flow_graph
    import matplotlib.pyplot as plt

    mmgraph = create_grid_graph(3, 4, 10)
    #
    fig, ax = plt.subplots()
    draw_flow_graph(ax, mmgraph.flow_graph)
    plt.show()
