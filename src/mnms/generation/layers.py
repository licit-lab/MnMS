from dataclasses import dataclass

from typing import Optional, Type, List

import numpy as np

from mnms.graph.layers import OriginDestinationLayer, SimpleLayer
from mnms.graph.road import RoadDescriptor
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.vehicles.veh_type import Vehicle, Car


def generate_layer_from_roads(roads: RoadDescriptor,
                              layer_id: str,
                              veh_type:Type[Vehicle] = Car,
                              default_speed: float = 14,
                              mobility_services: Optional[List[AbstractMobilityService]] = None):

    layer = SimpleLayer(roads, layer_id, veh_type, default_speed, mobility_services)

    for n in roads.nodes:
        layer.create_node(f"{layer_id}_{n}", n, {})

    for lid, data in roads.sections.items():
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
                                           ny: Optional[int] = None):
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
            odlayer.create_destination_node(f"DESTINATION_{str(i + j * nx)}", pos)
            odlayer.create_origin_node(f"ORIGIN_{str(i + j * nx)}", pos)

    return odlayer


@dataclass
class BoundingBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float


def get_bounding_box(roads: RoadDescriptor):
    positions = np.array([node.position for node in roads.nodes.values()])
    return BoundingBox(np.min(positions[:, 0]),
                       np.min(positions[:, 1]),
                       np.max(positions[:, 0]),
                       np.max(positions[:, 1]))


def generate_bbox_origin_destination_layer(roads: RoadDescriptor, nx: int, ny: Optional[int] = None):
    bbox = get_bounding_box(roads)
    return generate_grid_origin_destination_layer(*bbox, nx, ny)
