from typing import List
from mnms.graph import MultiModalGraph
from mnms.graph.core import TransitLink, ConnectionLink


def reconstruct_path(mmgraph: MultiModalGraph, path:List[str]):
    res = list()
    last_res = None
    last_mob = None
    length = 0

    for ni in range(len(path) - 1):
        nj = ni + 1
        link = mmgraph.mobility_graph.links[(path[ni], path[nj])]
        if isinstance(link, ConnectionLink):
            for lid in link.reference_links:
                flow_link = mmgraph.flow_graph.links[mmgraph.flow_graph._map_lid_nodes[lid]]
                curr_res = flow_link.zone
                curr_mob = link.mobility_service
                if curr_res != last_res or curr_mob != last_mob:
                    if last_mob is not None:
                        res.append({"sensor": last_res, "mode": last_mob, "length": length})
                    length = flow_link.length
                    last_mob = curr_mob
                    last_res = curr_res
                else:
                    length += flow_link.length
        elif isinstance(link, TransitLink):
            res.append({"sensor": last_res, "mode": last_mob, "length": length})
            length = 0
            last_mob = None
            last_res = None


    res.append({"sensor": last_res, "mode": last_mob, "length": length})
    return res