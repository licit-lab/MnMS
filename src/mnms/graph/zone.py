from typing import Set, List, Annotated
from dataclasses import dataclass

import numpy as np

from mnms.tools.geometry import points_in_polygon

Point = Annotated[List[float], 2]
PointList = List[Point]


@dataclass(slots=True)
class Zone(object):
    id: str
    sections: Set[str]
    contour: PointList

    def is_inside(self, points: List[Point]):
        return points_in_polygon(self.contour, points)

    def centroid(self):
        arr = np.array(self.contour)
        length = arr.shape[0]
        sum_x = np.sum(arr[:, 0])
        sum_y = np.sum(arr[:, 1])
        return np.array([sum_x/length, sum_y/length])

@dataclass
class MLZone(object):
    id: str
    links: Set[str]
    contour: PointList

@dataclass
class LayerZone(object):
    """Zone for the AbstractLayer objects : it gathers links belonging to the same
    layer.
    """
    id: str
    links: Set[str]
    contour : PointList
    detour_ratio : float = 1.343

    def is_inside(self, points: List[Point]):
        return points_in_polygon(self.contour, points)

def construct_zone_from_contour(roads: "RoadDescriptor", id: str, contour: PointList, graph=None, zone_type='Zone'):
    sections = roads.sections if graph is None else graph.links
    nodes = roads.nodes if graph is None else graph.nodes
    section_centers = [0 for _ in range(len(sections))]
    section_ids = np.array([s for s in sections])

    for i, data in enumerate(sections.values()):
        up_pos = nodes[data.upstream].position
        down_pos = nodes[data.downstream].position
        section_centers[i] = np.array([(up_pos[0] + down_pos[0]) / 2., (up_pos[1] + down_pos[1]) / 2.])

    section_centers = np.array(section_centers)

    contour_array = np.array(contour)
    mask = points_in_polygon(contour_array, section_centers)
    zone_links = section_ids[mask].tolist()
    if graph is None:
        assert zone_type == 'Zone', 'Inconsistent arguments in construct_zone_from_contour function...'
        return Zone(id, zone_links, contour)
    else:
        assert zone_type in ['MLZone', 'LayerZone'], 'Unknown zone type argument in construct_zone_from_contour function...'
        if zone_type == 'MLZone':
            return MLZone(id, zone_links, contour)
        else:
            return LayerZone(id, zone_links, contour)


def construct_zone_from_sections(roads: "RoadDescriptor", _id: str, sections: List[str]):
    nodes = []
    for sec in sections:
        section = roads.sections[sec]
        nodes.append(roads.nodes[section.upstream].position)
        nodes.append(roads.nodes[section.downstream].position)

    nodes = np.array(nodes)

    min_x, min_y = np.min(nodes, axis=0)
    max_x, max_y = np.max(nodes, axis=0)
    bbox = [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]]
    return Zone(_id, set(sections), bbox)
