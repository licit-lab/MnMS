from operator import attrgetter
from itertools import count
import numpy as np
from random import choice


from hipop.shortest_path import dijkstra
from mnms.demand.user import User
from mnms.time import Time
from mnms.demand.manager import BaseDemandManager


def generate_random_demand(mlgraph: "MultiLayerGraph",
                           nb_user: int,
                           tstart="07:00:00",
                           tend="18:00:00",
                           min_cost=0,
                           cost_path=None,
                           distrib_time=np.random.uniform,
                           repeat=1, seed=None) -> BaseDemandManager:
    """Create a random demand by using the extremities of the mobility_graph as origin destination pair, the departure
    time use a distribution function to generate the departure between tstart and tend.

    Args:
        mmgraph: The graph use to generate the demand
        tstart: Lower bound of departure time
        tend: Upper boumd of departure time
        min_cost: Minimal cost to accept an origin destination pair
        cost_path: The name of the cost to use for shortest path
        distrib_time: Distribution function to generate random departure dates
        repeat: Repeat each origin destination pair
        seed: Random seed

    Returns:
        The generated demand

    """
    if cost_path is None:
        cost_path = "length"

    if seed is not None:
        np.random.seed(seed)

    tstart = Time(tstart).to_seconds()
    tend = Time(tend).to_seconds()

    demand = []
    origins = list(mlgraph.odlayer.origins.keys())
    destinations = list(mlgraph.odlayer.destinations.keys())
    uid = count(0)

    graph = mlgraph.graph
    user_count = 0

    map_layer_services = {lid:list(layer.mobility_services.keys())[0] for lid, layer in mlgraph.layers.items()}
    map_layer_services["TRANSIT"] = "WALK"

    while user_count <= nb_user:
        unode = choice(origins)
        dnode = choice(destinations)
        try:
            _, path_cost = dijkstra(graph, unode, dnode, cost_path, map_layer_services)
        except ValueError as ex:
            log.error(f'HiPOP.Error: {ex}')
            sys.exit(-1)
        if min_cost <= path_cost < float('inf'):
            demand.extend([User(str(next(uid)), unode, dnode, Time.from_seconds(distrib_time(tstart, tend))) for _ in
                           range(repeat)])
            user_count+=repeat

    demand.sort(key=attrgetter('departure_time'))

    uid = count(0)
    for u in demand:
        u.id = str(next(uid))
    return BaseDemandManager(demand)


if __name__ == "__main__":

    from mnms.generation.mlgraph import generate_manhattan_passenger_car
    from mnms.io.graph import save_odlayer, save_graph

    mlgraph = generate_manhattan_passenger_car(20, 100)

    demand = generate_random_demand(mlgraph,
                                    500,
                                    min_cost=300)

    demand.to_csv("random_demand_20x20.csv")
    save_odlayer(mlgraph.odlayer, "odlayer_20x20.json")
    save_graph(mlgraph, "manhattan_20x20.json")
