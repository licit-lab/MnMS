from operator import attrgetter

import numpy as np

from mnms.graph.algorithms import compute_shortest_path
from mnms.demand.user import User
from mnms.tools.time import Time
from mnms.demand.manager import BaseDemandManager
from mnms.tools.exceptions import PathNotFound


def create_random_demand(mmgraph: "MultiModalGraph", tstart="07:00:00", tend="18:00:00", min_cost=0, cost_path=None, distrib_time=np.random.uniform, repeat=1, seed=None) -> BaseDemandManager:
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
        cost_path = "_default"

    if seed is not None:
        np.random.seed(seed)

    tstart = Time(tstart).to_seconds()
    tend = Time(tend).to_seconds()

    demand = []
    extremities = mmgraph.get_extremities()
    uid = 0
    for unode in extremities:
        for dnode in extremities:
            if unode != dnode:
                vuser = User(str(uid),unode,dnode,Time.fromSeconds(distrib_time(tstart, tend)))
                try:
                    cost = compute_shortest_path(mmgraph, vuser, cost_path, algorithm='astar')
                    if cost >= min_cost and cost < float('inf'):
                        demand.extend([User(str(uid), unode, dnode, Time.fromSeconds(distrib_time(tstart, tend))) for _ in range(repeat)])
                        uid += 1
                except PathNotFound:
                    pass

    demand.sort(key=attrgetter('departure_time'))
    return BaseDemandManager(demand)
