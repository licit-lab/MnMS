from random import randrange
from mgraph.cpp import generate_manhattan, dijkstra, parallel_dijkstra


g = generate_manhattan(3, 10)

print(dijkstra(g, "SOUTH_0", "NORTH_0", "length"))



N = int(3e6)

origins = ["SOUTH_0"]*N
dests = ["NORTH_0"]*N
available_labels = [set() for _ in range(N)]

print("Launch")
parallel_dijkstra(g, origins, dests, "length", available_labels, 3)
print("Done")
