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


def construct_zone_from_contour(roads: "RoadDescriptor", _id: str, contour: PointList):
    section_centers = [0 for _ in range(len(roads.sections))]
    section_ids = np.array([s for s in roads.sections])

    for i, data in enumerate(roads.sections.values()):
        up_pos = roads.nodes[data.upstream].position
        down_pos = roads.nodes[data.downstream].position
        section_centers[i] = np.array([(up_pos[0] + down_pos[0]) / 2., (up_pos[1] + down_pos[1]) / 2.])

    section_centers = np.array(section_centers)

    contour_array = np.array(contour)
    mask = points_in_polygon(contour_array, section_centers)
    zone_links = section_ids[mask].tolist()
    return Zone(_id, zone_links, contour)


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
