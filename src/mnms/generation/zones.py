from mnms.graph.road import RoadDescriptor
from mnms.tools.geometry import get_bounding_box
from mnms.graph.zone import construct_zone_from_contour


def generate_one_zone(zid: str, roads: RoadDescriptor):
    """
    Generate a simple zone from the bounding box of the RoadDedscriptor

    Args:
        zid: The id of the zone
        roads: The RoadDescriptor

    Returns:
        The generated RoadDescriptor

    """
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

def generate_grid_zones(zid_prefix: str, roads: RoadDescriptor, Nx: int, Ny: int, mlgraph=None):
    """
    Generate Nx * Ny rectangle pricing zones within the bounding box of the RoadDescriptor
    on the RoadDescriptor.

    Args:
        zid_prefix: The prefix for the ids of the zones
        roads: The RoadDescriptor
        Nx: number of zones along the x axis
        Ny: number of zones along the y axis
        mlgraph: specified when the zoning should be built on the MultiLayerGraph

    Returns:
        The generated zones (Zone objects are built on RoadDescriptor, MLZone objects are
        built on the MultiLayerGraph)
    """
    if mlgraph is not None:
        roads = mlgraph.roads
    bbox = get_bounding_box(roads) if mlgraph is None else get_bounding_box(mlgraph.roads)
    dx = (bbox.xmax - bbox.xmin) / Nx
    dy = (bbox.ymax - bbox.ymin) / Ny
    zones = []
    startx = bbox.xmin - 1
    starty = bbox.ymin - 1
    for nx in range(Nx):
        for ny in range(Ny):
            if nx == Nx - 1 and ny < Ny - 1:
                c = [[startx + nx * dx, starty + ny * dy],
                             [startx + (nx+1) * dx + 2, starty + ny * dy],
                             [startx + (nx+1) * dx + 2, starty + (ny+1) * dy],
                             [startx + nx * dx, starty + (ny+1) * dy]]
            elif nx < Nx - 1 and ny == Ny - 1:
                c = [[startx + nx * dx, starty + ny * dy],
                             [startx + (nx+1) * dx, starty + ny * dy],
                             [startx + (nx+1) * dx, starty + (ny+1) * dy + 2],
                             [startx + nx * dx, starty + (ny+1) * dy + 2]]
            elif nx == Nx - 1 and ny == Ny - 1:
                c = [[startx + nx * dx, starty + ny * dy],
                             [startx + (nx+1) * dx + 2, starty + ny * dy],
                             [startx + (nx+1) * dx + 2, starty + (ny+1) * dy + 2],
                             [startx + nx * dx, starty + (ny+1) * dy + 2]]
            else:
                c = [[startx + nx * dx, starty + ny * dy],
                             [startx + (nx+1) * dx, starty + ny * dy],
                             [startx + (nx+1) * dx, starty + (ny+1) * dy],
                             [startx + nx * dx, starty + (ny+1) * dy]]
            graph = None if mlgraph is None else mlgraph.graph
            zone_type = 'Zone' if mlgraph is None else 'MLZone'
            zones.append(construct_zone_from_contour(roads, zid_prefix+str(nx)+'-'+str(ny), c, graph=graph, zone_type=zone_type))
    return zones
