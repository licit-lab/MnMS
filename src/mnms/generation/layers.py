from typing import Optional, Type, List, Annotated

import numpy as np

from mnms.graph.layers import AbstractLayer
from mnms.graph.layers import OriginDestinationLayer, SimpleLayer
from mnms.graph.road import RoadDescriptor
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.tools.geometry import get_bounding_box, points_in_polygon
from mnms.vehicles.veh_type import Vehicle, Car

Point = Annotated[List[float], 2]
PointList = List[Point]

def generate_layer_from_roads(roads: RoadDescriptor,
                              layer_id: str,
                              class_layer = SimpleLayer,
                              veh_type:Type[Vehicle] = Car,
                              default_speed: float = 14,
                              mobility_services: Optional[List[AbstractMobilityService]] = None,
                              banned_nodes: List[str] = None,
                              banned_sections: List[str] = None) -> AbstractLayer:
    """
    Generate a whole layer from the RoadDescriptor.

    Args
        roads: The roads object
        layer_id: the id of the generated layer
        veh_type: the type of vehicle
        default_speed: the default speed
        mobility_services: the mobility services on the generated layer
        banned_nodes: specifies the list of nodes for which no layer node should
                      be created
        banned_sections: specifies the list of sections for which no layer link
                         should be created

    Returns:
        The generated Layer
    """

    layer = class_layer(roads, layer_id, veh_type, default_speed, mobility_services)

    for n in roads.nodes:
        if banned_nodes is None or (banned_nodes is not None and n not in banned_nodes):
            layer.create_node(f"{layer_id}_{n}", n, {})

    for lid, data in roads.sections.items():
        if banned_sections is None or (banned_sections is not None and lid not in banned_sections):
            cost = {}
            if mobility_services is not None:
                for mservice in mobility_services:
                    cost[mservice.id] = {'length': data.length}
            else:
                cost["_DEFAULT"] = {'length': data.length}

            layer.create_link(f"{layer_id}_{lid}",
                          f"{layer_id}_{data.upstream}",
                          f"{layer_id}_{data.downstream}",
                          cost,
                          [lid])
    return layer


def generate_matching_origin_destination_layer(roads: RoadDescriptor, with_stops: bool = True):

    odlayer = OriginDestinationLayer()

    for node in roads.nodes.values():
        odlayer.create_origin_node(f"ORIGIN_{node.id}", node.position)
        odlayer.create_destination_node(f"DESTINATION_{node.id}", node.position)

    if with_stops:
        for stop in roads.stops.values():
            odlayer.create_origin_node(f"ORIGIN_{stop.id}", stop.absolute_position)
            odlayer.create_destination_node(f"DESTINATION_{stop.id}", stop.absolute_position)

    return odlayer


def generate_grid_origin_destination_layer(xmin: float,
                                           ymin: float,
                                           xmax: float,
                                           ymax: float,
                                           nx: int,
                                           ny: Optional[int] = None,
                                           polygon: Optional[PointList] = None):
    """
    Generate a rectangular structured grid for the OriginDestinationLayer

    Args:
        xmin: the min x of the grid
        ymin: the min y of the grid
        xmax: the max x of the grid
        ymax: the max y of the grid
        nx: the number of point in the x direction
        ny: the number of point in the y direction
        polygon: optional arg that specifies a polygon outside of which the
                 origin and destination should not be created

    Returns:
        The OriginDestinationLayer

    """
    if ny is None:
        ny = nx

    x_dist = xmax - xmin
    y_dist = ymax - ymin

    dx = x_dist / nx
    dy = y_dist / ny

    odlayer = OriginDestinationLayer()

    for j in range(ny):
        for i in range(nx):
            pos = np.array([xmin + i * dx, ymin + j * dy])
            if polygon is not None:
                if not points_in_polygon(np.array(polygon), [pos])[0]:
                    continue
            odlayer.create_destination_node(f"DESTINATION_{str(i + j * nx)}", pos)
            odlayer.create_origin_node(f"ORIGIN_{str(i + j * nx)}", pos)

    return odlayer


def generate_bbox_origin_destination_layer(roads: RoadDescriptor, nx: int, ny: Optional[int] = None, polygon: Optional[PointList] = None) -> OriginDestinationLayer:
    """
    Generate a grid OriginDestinationLayer based on the bounding box of the roads nodes

    Args:
        roads: The OriginDestinationLayer from which the odlayer is created
        nx: The number of point in the x direction
        ny: The number of point in the y direction
        polygon: Optional arg that specifies a polygon outside of which the origins and destinations are not created

    Returns:
        The generated layer

    """
    bbox = get_bounding_box(roads)
    return generate_grid_origin_destination_layer(bbox.xmin - 1, bbox.ymin - 1, bbox.xmax + 1, bbox.ymax + 1, nx, ny, polygon=polygon)
