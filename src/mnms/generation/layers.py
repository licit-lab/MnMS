from typing import Optional, Type, List

import numpy as np

from mnms.graph.layers import OriginDestinationLayer, SimpleLayer
from mnms.graph.road import RoadDataBase
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.vehicles.veh_type import Vehicle, Car


def generate_layer_from_roads(roaddb: RoadDataBase,
                              layer_id: str,
                              veh_type:Type[Vehicle] = Car,
                              default_speed: float = 14,
                              mobility_services: Optional[List[AbstractMobilityService]] = None):

    layer = SimpleLayer(layer_id, roaddb, veh_type, default_speed, mobility_services)


    for n, pos in roaddb.nodes.items():
        layer.create_node(f"{layer_id}_{n}", n, {})

    for lid, data in roaddb.sections.items():
        layer.create_link(f"{layer_id}_{lid}",
                          f"{layer_id}_{data['upstream']}",
                          f"{layer_id}_{data['downstream']}",
                          {'length': data['length']},
                          [lid])
    return layer


def generate_matching_origin_destination_layer(roaddb: RoadDataBase, with_stops: bool = True):

    odlayer = OriginDestinationLayer()

    for nid, pos in roaddb.nodes.items():
        odlayer.create_origin_node(f"ORIGIN_{nid}", pos)
        odlayer.create_destination_node(f"DESTINATION_{nid}", pos)

    if with_stops:
        for sid, d in roaddb.stops.items():
            pos = d['absolute_position']
            odlayer.create_origin_node(f"ORIGIN_{sid}", pos)
            odlayer.create_destination_node(f"DESTINATION_{sid}", pos)

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


def get_bounding_box(roaddb: RoadDataBase):
    positions = np.array([n for n in roaddb.nodes.values()])
    return np.min(positions[0, :]), np.min(positions[1, :]), np.max(positions[0, :]), np.max(positions[1, :])


def generate_bbox_origin_destination_layer(roaddb: RoadDataBase, nx: int, ny: Optional[int] = None):
    bbox = get_bounding_box(roaddb)
    return generate_grid_origin_destination_layer(*bbox, nx, ny)