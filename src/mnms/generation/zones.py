from mnms.graph.road import RoadDescriptor
from mnms.tools.geometry import get_bounding_box
from mnms.graph.zone import construct_zone_from_contour


def generate_one_zone(zid: str, roads: RoadDescriptor):
    bbox = get_bounding_box(roads)
    bbox.xmin -= 1
    bbox.ymin -= 1
    bbox.xmax += 1
    bbox.ymax += 1
    contour = [[bbox.xmin, bbox.ymin],
               [bbox.xmax, bbox.ymin],
               [bbox.xmax, bbox.ymax],
               [bbox.xmin, bbox.ymax]]
    return construct_zone_from_contour(roads, zid, contour)
