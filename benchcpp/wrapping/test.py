from cppgraph import OrientedGraph


g = OrientedGraph()
g.add_node("0", 0, 0)
g.add_node("1", 1, 0)

g.add_link("0_1", "0", "1", {"test": 42})