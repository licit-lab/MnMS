from mnms.graph.algorithms import compute_shortest_path
from mnms.tools.time import Time

import numpy as np

def create_random_demand(mmgraph: "MultiModalGraph", tstart="07:00:00", tend="18:00:00", min_cost=0, cost_path=None, distrib_time=np.random.uniform, repeat=1):
    if cost_path is None:
        cost_path = "_default"

    tstart = Time(tstart).to_seconds()
    tend = Time(tend).to_seconds()

    demand = []
    extremities = mmgraph.get_extremities()
    for unode in extremities:
        for dnode in extremities:
            if unode != dnode:
                cost, path = compute_shortest_path(mmgraph, unode, dnode, cost_path)
                if cost < float("inf"):
                    if cost >= min_cost:
                        demand.extend([[Time.fromSeconds(distrib_time(tstart, tend)) ,path]  for _ in range(repeat)])
    return demand
