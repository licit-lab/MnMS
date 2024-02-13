import osmnx as ox

graph = ox.graph_from_place('Lyon, France', network_type="drive")

tags = {'station': 'subway'}
geometries = ox.features_from_place('Lyon, France', tags=tags)

for inode, node in graph.nodes.items():
    print(inode, node)

# for iedge, edge in graph.edges.items():
#     print(iedge, edge)

print("Nodes count:", len(graph.nodes.items()))
print("Edges count:", len(graph.edges.items()))

#for index, geometry in geometries.items():
    #print(geometry)