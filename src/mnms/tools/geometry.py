from dataclasses import dataclass
from collections import defaultdict
from shapely.geometry import Polygon, mapping
from scipy.spatial import Voronoi
import numpy as np
from typing import List, Annotated

Point = Annotated[List[float], 2]
PointList = List[Point]


@dataclass
class BoundingBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    def polygon(self):
        """Method that returns the bounding box polygon.
        """
        return [[self.xmin, self.ymin], [self.xmax, self.ymin],
            [self.xmax, self.ymax], [self.xmin, self.ymax]]


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

def voronoi_zones(points: PointList, bbox: BoundingBox):
    """Method that produces a list of polygons corresponding to the Voronoi regions
    of the points passed. It is based on Gareth Rees's function.

    Args:
        -points: input points to compute the Voronoi diagram of
        -bbox: bounding box of the output polygons

    Returns:
        -polygons: the list of Voronoi zones contours
    """
    # Compute the Voronoi diagram of the points
    voronoi = Voronoi(points)

    # Compute the directions of inifinite ridges
    centroid = voronoi.points.mean(axis=0)
    ridge_direction = defaultdict(list)
    for (p, q), rv in zip(voronoi.ridge_points, voronoi.ridge_vertices):
        u, v = sorted(rv)
        if u == -1:
            # Infinite ridge starting at ridge point with index v,
            # equidistant from input points with indexes p and q
            tangent = voronoi.points[q] - voronoi.points[p]
            normal = np.array([-tangent[1], tangent[0]]) / np.linalg.norm(tangent)
            midpoint = voronoi.points[[p, q]].mean(axis=0)
            direction = np.sign(np.dot(midpoint - centroid, normal)) * normal
            ridge_direction[p, v].append(direction)
            ridge_direction[q, v].append(direction)

    # Build the Voronoi polygons
    polygons = []
    for i, r in enumerate(voronoi.point_region):
        region = voronoi.regions[r]
        if -1 not in region:
            # Finite region, nothing more to do
            pol = Polygon(voronoi.vertices[region])
            pol = [list(c) for c in mapping(pol)['coordinates'][0][:-1]]
            polygons.append(pol)
            continue
        # Infinite region
        inf = region.index(-1)              # Index of vertex at infinity
        j = region[(inf - 1) % len(region)] # Index of previous vertex
        k = region[(inf + 1) % len(region)] # Index of next vertex
        if j == k:
            # Region has one Voronoi vertex with two ridges
            dir_j, dir_k = ridge_direction[i, j]
        else:
            # Region has two Voronoi vertices, each with one ridge
            dir_j, = ridge_direction[i, j]
            dir_k, = ridge_direction[i, k]

        # Length of ridges needed for the extra edge to fill the bounding box
        diameter = max(bbox.xmax-bbox.xmin, bbox.ymax-bbox.ymin)
        length = 2 * diameter / np.linalg.norm(dir_j + dir_k)

        # Polygon consists of finite part plus an extra edge
        finite_part = voronoi.vertices[region[inf + 1:] + region[:inf]]
        extra_edge = [voronoi.vertices[j] + dir_j * length,
                      voronoi.vertices[k] + dir_k * length]
        pol = Polygon(np.concatenate((finite_part, extra_edge)))

        # Reduce polygon to the bounding box
        pol = pol.intersection(Polygon(bbox.polygon()))
        pol = [list(c) for c in mapping(pol)['coordinates'][0][:-1]]
        polygons.append(pol)

    return polygons
