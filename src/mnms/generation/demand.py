from operator import attrgetter
from itertools import count
import numpy as np
from random import shuffle, choice


from hipop.shortest_path import dijkstra
from mnms.demand.user import User
from mnms.time import Time
from mnms.demand.manager import BaseDemandManager
from mnms.tools.exceptions import PathNotFound


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

    Parameters
    ----------
    mmgraph: MultiModalGraph
        The graph use to generate the demand
    tstart: Time
        Lower bound of departure time
    tend: Time
        Upper boumd of departure time
    min_cost: float
        Minimal cost to accept an origin destination pair
    cost_path: str
        The name of the cost to use for shortest path
    distrib_time: function
        Distribution function to generate random departure dates
    repeat: int
        Repeat each origin destination pair
    seed: int
        Random seed

    Returns
    -------
    BaseDemandManager

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
    while user_count <= nb_user:
        unode = choice(origins)
        dnode = choice(destinations)

        _, path_cost = dijkstra(graph, unode, dnode, cost_path)
        if min_cost <= path_cost < float('inf'):
            demand.extend([User(str(next(uid)), unode, dnode, Time.fromSeconds(distrib_time(tstart, tend))) for _ in
                           range(repeat)])
            user_count+=repeat

    demand.sort(key=attrgetter('departure_time'))

    uid = count(0)
    for u in demand:
        u.id = str(next(uid))
    return BaseDemandManager(demand)
