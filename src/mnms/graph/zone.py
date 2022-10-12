from typing import Set, List, Annotated
from dataclasses import dataclass

import numpy as np

Point = Annotated[List[float], 2]
PointList = List[Point]


@dataclass(slots=True)
class Zone(object):
    id: str
    sections: Set[str]
    contour: PointList

    def is_inside(self, points: List[Point]):
        return points_in_polygon(self.contour, [points])


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
