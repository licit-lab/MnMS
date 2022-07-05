#include "helpers.h"

#include <mgraph/graph.h>
#include <mgraph/shortest_path.h>


int testDijkstra2(int argc, char *argv[])
{   
    OrientedGraph G;

    G.AddNode("0", 0, 0);
    G.AddNode("1", 1, 0);
    G.AddNode("2", 1, 1);
    G.AddNode("3", 0, 1, {{"0", {"2"}}});

    G.AddLink("0_1", "0", "1", 1, {{"time", 12}});
    G.AddLink("1_2", "1", "2", 1, {{"time", 13}});
    G.AddLink("0_3", "0", "3", 1, {{"time", 12}});
    G.AddLink("3_2", "3", "2", 1, {{"time", 12}});

    auto path = dijkstra(G, "0", "2", "time");

    assertTrue(path.second==25, "Path cost not equal to 25");
    assertTrue(path.first==std::vector<std::string>{"0", "1", "2"}, "Path nodes not equal to 0, 1, 2");

    return 0;
}

