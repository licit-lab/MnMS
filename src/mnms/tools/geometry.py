from dataclasses import dataclass

import numpy as np


@dataclass
class BoundingBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float


def get_bounding_box(roads: "RoadDescriptor", graph = None):
    if graph is None:
        positions = np.array([node.position for node in roads.nodes.values()])
    else:
        positions = np.array([node.position for node in graph.nodes.values()])
    return BoundingBox(np.min(positions[:, 0]),
                       np.min(positions[:, 1]),
                       np.max(positions[:, 0]),
                       np.max(positions[:, 1]))


def points_in_polygon(polygon, pts):
    if len(pts) == 0:
        return []
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

def polygon_area(polygon):
    """Method that computes the area of a polygon based on Schoelace formula.

    Args:
        -polygon: defined by a list of points
    """
    x = [p[0] for p in polygon]
    y = [p[1] for p in polygon]
    area = 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
    return area
