from importlib.resources import path
from mgraph import OrientedGraph, k_shortest_path, parallel_k_shortest_path
from pprint import pprint

G = OrientedGraph()

G.add_node("0", 0, 0, {})
G.add_node("1", 1, 0, {})
G.add_node("2", 1, 1, {})
G.add_node("3", 0, 1, {})

G.add_link("0_1", "0", "1", 1, {"time": 10})
G.add_link("0_3", "0", "3", 1,{"time": 11})
G.add_link("0_2", "0", "2", 1.44,{"time": 10})
G.add_link("1_2", "1", "2", 4,{"time": 10})
G.add_link("3_2", "3", "2", 5, {"time": 9})
G.add_link("1_3", "1", "3", 1, {"time": 10})

# paths = k_shortest_path(G, "0", "2", "time", set(), -100, 100, 4)
# print(paths)


N = int(1e6)
origins = ["0" for _ in range(N)]
destinations = ["2" for _ in range(N)]
labels = [set() for _ in range(N)]


paths = parallel_k_shortest_path(G, origins, destinations, "time", labels, 0, 100, 3, 8)
pprint(paths[-30:])
                                                     