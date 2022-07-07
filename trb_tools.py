from typing import List, Dict

import numpy as np
from mnms.graph.core import MultiModalGraph
from mnms.graph.shortest_path import dijkstra


class Zone(object):
    def __init__(self, id, links, depot):
        self.id = id
        self.links = links
        self.depot = depot


def points_in_polygon(polygon, pts):
    pts = np.asarray(pts, dtype='float32')
    polygon = np.asarray(polygon, dtype='float32')
    contour2 = np.vstack((polygon[1:], polygon[:1]))
    test_diff = contour2 - polygon
    mask1 = (pts[:, None] == polygon).all(-1).any(-1)
    m1 = (polygon[:, 1] > pts[:, None, 1]) != (contour2[:, 1] > pts[:, None, 1])
    slope = ((pts[:, None, 0] - polygon[:, 0]) * test_diff[:, 1]) - (
                test_diff[:, 0] * (pts[:, None, 1] - polygon[:, 1]))
    m2 = slope == 0
    mask2 = (m1 & m2).any(-1)
    m3 = (slope < 0) != (contour2[:, 1] < polygon[:, 1])
    m4 = m1 & m3
    count = np.count_nonzero(m4, axis=-1)
    mask3 = ~(count % 2 == 0)
    mask = mask1 | mask2 | mask3
    return mask


def clip_graph(G: MultiModalGraph, polygonal_envelopes: Dict[str, List[List[float]]]):
    links_centers = [0 for _ in range(len(G.flow_graph.links))]
    links_ids = np.array([l.id for l in G.flow_graph.links.values()])
    all_nodes = G.flow_graph.nodes

    zones = []

    for i, l in enumerate(G.flow_graph.links.values()):
        up_pos = all_nodes[l.upstream].pos
        down_pos = all_nodes[l.downstream].pos
        links_centers[i] = np.array([(up_pos[0]+down_pos[0])/2., (up_pos[1]+down_pos[1])/2.])

    links_centers = np.array(links_centers)

    for zid, z in polygonal_envelopes.items():
        z = np.array(z)
        mask = points_in_polygon(z, links_centers)
        zone_links = links_ids[mask].tolist()

        size = z.shape[0]
        sum_x = np.sum(z[:, 0])
        sum_y = np.sum(z[:, 1])
        centroid = np.array([sum_x / size, sum_y / size])

        nodes_in_zone = set()
        for l in zone_links:
            link = G.flow_graph.get_link(l)
            nodes_in_zone.add(link.upstream)
            nodes_in_zone.add(link.downstream)
        nodes_in_zone = list(nodes_in_zone)
        nodes_in_zone_pos = np.array([all_nodes[n].pos for n in nodes_in_zone])

        closest_ind = np.argmin(np.linalg.norm(nodes_in_zone_pos - centroid, axis=1))
        depot = nodes_in_zone[closest_ind]
        zones.append(Zone(zid, zone_links, depot))

    return zones



if __name__ == "__main__":
    from mnms.graph.generation import manhattan
    from mnms.tools.render import draw_flow_graph

    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon


    G = manhattan(4, 1)
    zones = {"Z1": [[-1.1, -1.1], [1.5, -1.1], [1.5, 1.5], [-1.1, 1.5]],
             "Z2": [[1.5, -1.1], [4.1, -1.1], [4.1, 1.5], [1.5, 1.5]],
             "Z3": [[-1.1, 1.5], [1.5, 1.5], [1.5, 4.1], [-1.1, 4.1]],
             "Z4": [[1.5, 1.5], [4.1, 1.5], [4.1, 4.1], [1.5, 4.1]]}

    clipped_zones = clip_graph(G, zones)


    fig, ax = plt.subplots()
    draw_flow_graph(ax, G.flow_graph)
    for z, c  in zip(zones.values(), ['red', 'blue', 'green', 'yellow']):
        poly = Polygon(z, closed=False, alpha=0.3, facecolor=c)
        ax.add_patch(poly)
    plt.show()



