from typing import Optional, Type, List, Annotated

import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn import preprocessing
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from mnms.graph.abstract import AbstractLayer
from mnms.graph.layers import OriginDestinationLayer, SimpleLayer
from mnms.graph.road import RoadDescriptor
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.tools.geometry import get_bounding_box, points_in_polygon
from mnms.vehicles.veh_type import Vehicle, Car

Point = Annotated[List[float], 2]
PointList = List[Point]


def generate_layer_from_roads(roads: RoadDescriptor,
                              layer_id: str,
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

    layer = SimpleLayer(roads, layer_id, veh_type, default_speed, mobility_services)

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


# WIP
def generate_cluster_origin_destination_layer(roads: RoadDescriptor, max_clusters: int):

    odlayer = OriginDestinationLayer()

    df_nodes = pd.DataFrame(columns=["id", "x", "y"])

    for node in roads.nodes.values():
        new_node = {"id": node.id, "x": node.position[0], "y": node.position[1]}
        df_nodes = df_nodes.append(new_node, ignore_index=True)

    # X_train and y_train : features and target values for training set
    # X_test and y_test : features and target values for testing test
    # 33% of the data will be used for testing and 67% will be used for training.
    X_train, X_test, y_train, y_test = train_test_split(df_nodes[["x", "y"]], test_size=0.33, random_state=0)

    X_train_norm = preprocessing.normalize(X_train)
    X_test_norm = preprocessing.normalize(X_test)

    kmeans = KMeans(n_clusters=3, random_state=0, n_init='auto')
    kmeans.fit(X_train_norm)

    silhouette_score(X_train_norm, kmeans.labels_, metric='euclidean')

    K = range(2, max_clusters) #number of clusters, 2 to int specified in parameter
    fits = []
    score = []

    for k in K:
        # train the model for current value of k on training data
        model = KMeans(n_clusters=k, random_state=0, n_init='auto').fit(X_train_norm)
        # append the model to fits
        fits.append(model)
        # Append the silhouette score to scores
        score.append(silhouette_score(X_train_norm, model.labels_, metric='euclidean'))

    centroids = kmeans.cluster_centers_

    id_centroid = 0
    for centroid in centroids:
        pos_centroid = np.ndarray((centroid[0], centroid[1]))
        odlayer.create_origin_node(f"ORIGIN_{id_centroid}", pos_centroid)
        odlayer.create_destination_node(f"DESTINATION_{id_centroid}", pos_centroid)
        id_centroid = id_centroid + 1

    return odlayer