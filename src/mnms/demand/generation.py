from operator import attrgetter

import numpy as np

from mnms.graph.algorithms import compute_shortest_path
from mnms.demand.user import User
from mnms.tools.time import Time
from mnms.demand.manager import BaseDemandManager


def create_random_demand(mmgraph: "MultiModalGraph", tstart="07:00:00", tend="18:00:00", min_cost=0, cost_path=None, distrib_time=np.random.uniform, repeat=1, seed=None):
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
                cost = compute_shortest_path(mmgraph, vuser, cost_path, algorithm='astar')
                if cost < float("inf"):
                    if cost >= min_cost:
                        demand.extend([User(str(uid), unode, dnode, Time.fromSeconds(distrib_time(tstart, tend))) for _ in range(repeat)])
                        uid += 1
    demand.sort(key=attrgetter('departure_time'))
    return BaseDemandManager(demand)
