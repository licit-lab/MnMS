from dataclasses import dataclass

import numpy as np


@dataclass
class BoundingBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float


def get_bounding_box(roads: "RoadDescriptor"):
    positions = np.array([node.position for node in roads.nodes.values()])
    return BoundingBox(np.min(positions[:, 0]),
                       np.min(positions[:, 1]),
                       np.max(positions[:, 0]),
                       np.max(positions[:, 1]))


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
