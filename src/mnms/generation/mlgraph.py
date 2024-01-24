from mnms.generation.roads import generate_manhattan_road
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.graph.layers import MultiLayerGraph


def generate_manhattan_passenger_car(n, link_length, resid="RES") -> MultiLayerGraph:
    """

    Parameters
    ----------
    n
    link_length
    resid

    Returns
    -------

    """
    roads = generate_manhattan_road(n, link_length, resid)
    layer_car = generate_layer_from_roads(roads,
                                          "CAR",
                                          mobility_services=[PersonalMobilityService()])

    odlayer = generate_matching_origin_destination_layer(roads)

    mlgraph = MultiLayerGraph([layer_car],
                              odlayer,
                              1e-5)

    return mlgraph
