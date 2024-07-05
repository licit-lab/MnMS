import multiprocessing
import json
import time

from hipop.shortest_path import parallel_dijkstra, parallel_dijkstra_single_source, floyd_warshall

def compute_all_shortest_paths_naive(graph, chosen_mservice, layer_name, outfile):
    """Fonction that pre-computes the shortest paths for each pair of nodes of the
    graph of a layer and write them to a file. By shortest we mean in distance.
    It is a naive approach that launches in parallel dijkstra for all pairs.

    Args:
        -graph: graph of the layer
        -chosen_mservice: dict with a unique element {'layer_name': 'mob_service_name'}
        -layer_name: name of the layer
        -outfile: file where the shortest paths will be saved
    """
    # Launch parallel dijkstra on all od pairs
    all_ods = [(n1,n2) for n1 in graph.nodes for n2 in graph.nodes if n1 != n2]
    origins = [t[0] for t in all_ods]
    destinations = [t[1] for t in all_ods]
    print(f'There are {len(origins)} shortest paths to compute...')

    paths = parallel_dijkstra(graph,
        origins,
        destinations,
        [chosen_mservice]*len(origins),
        'length',
        multiprocessing.cpu_count(),
        [{layer_name}]*len(origins))

    # Build a dict of shortest paths
    sps = {}
    for i,(o,d) in enumerate(all_ods):
        if o in sps.keys():
            sps[o][d] = paths[i][0][0]
        else:
            sps[o] = {d: paths[i][0][0]}

    # Dump dict into json
    with open(outfile, 'w') as f:
        json.dump(sps, f)

def compute_all_shortest_paths_floyd_warshall(graph, chosen_mservice, layer_name, outfile):
    """Fonction that pre-computes the shortest paths for each pair of nodes of the
    graph of a layer and write them to a file. By shortest we mean in distance.
    It launches the Floyd-Warshall algorithm to do so.

    Args:
        -graph: graph of the layer
        -chosen_mservice: dict with a unique element {'layer_name': 'mob_service_name'}
        -layer_name: name of the layer
        -outfile: file where the shortest paths will be saved
    """
    # Call Floyd Warshall
    st = time.time()
    pair = floyd_warshall(graph,
                     'length',
                     chosen_mservice,
                     {layer_name})
    print(f'Flyod-Warshall done in {time.time()-st}')

    # Create the shortest paths trees
    st = time.time()
    prev_table = pair[0]
    vnodemap = pair[1]
    spts = {}
    null = max(list(vnodemap.keys())) + 1
    for v, node in vnodemap.items():
        spt = {}
        for v_, node_ in vnodemap.items():
            if prev_table[v][v_] == null:
                spt[node_] = ''
            else:
                spt[node_] = vnodemap[prev_table[v][v_]]
        spts[node] = spt
    print(f'Building of shortest paths trees done in {time.time()-st}')

    # Dump them into json file
    with open(outfile, 'w') as f:
        json.dump(spts, f)


def compute_all_shortest_paths(graph, chosen_mservice, layer_name, outfile):
    """Fonction that pre-computes the shortest paths for each pair of nodes of the
    graph of a layer and write them to a file. By shortest we mean in distance.
    It launches in parallel the single source dijkstra for all pairs.

    Args:
        -graph: graph of the layer
        -chosen_mservice: dict with a unique element {'layer_name': 'mob_service_name'}
        -layer_name: name of the layer
        -outfile: file where the shortest paths will be saved
    """
    origins = list(graph.nodes.keys())
    st = time.time()
    spts = parallel_dijkstra_single_source(graph,
                      origins,
                      [chosen_mservice]*len(origins),
                      'length',
                      multiprocessing.cpu_count(),
                      [{layer_name}]*len(origins))
    print(f'Done in {time.time()-st}')
    spts_dict = {}
    for i,o in enumerate(origins):
        spts_dict[o] = spts[i]

    # Dump dict into json the shortest path tree, not the paths as it is smaller
    # in memory size
    with open(outfile, 'w') as f:
        json.dump(spts_dict, f)

def decode_shortest_path_tree(spts, origin, destination):
    """Function to build the shortest path from the shortest path tree.

    Args:
        -spt: the shortest path tree
        -origin: origin of the shortest path
        -destination: destination of the shortest path

    Returns:
        -sp: the shortest path (list of nodes)
    """
    spt = spts[origin]
    d = destination
    path = [d]
    valid = True
    while d != origin:
        d = spt[d]
        if d == '':
            return []
        path.append(d)
    path = list(reversed(path))

    return path
