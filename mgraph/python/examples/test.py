from mgraph.cpp import generate_manhattan, dijkstra, parallel_dijkstra

from time import time

g = generate_manhattan(100, 10)

print(dijkstra(g, "NORTH_0", "EAST_0", "length"))

# N = int(3000)

# origins = ["NORTH_0"]*N
# dests = ["EAST_0"]*N
# available_labels = [set() for _ in range(N)]

# print("Launch")
# start = time()
# res = parallel_dijkstra(g, origins, dests, "length", 8)
# end = time()
# print("Done", f"[{end-start} s]")

# print(res[0])
