#include "helpers.h"

#include <mgraph/graph.h>
#include <mgraph/shortest_path.h>



int testKShortestPath(int argc, char *argv[])
{
    OrientedGraph G;

    G.AddNode("0", 0, 0);
    G.AddNode("1", 1, 1);
    G.AddNode("2", 1, -1);
    G.AddNode("3", 2, 0);
    G.AddNode("4", 2, 1);

    G.AddLink("0_1", "0", "1", 1, {{"time", 14}});
    G.AddLink("1_3", "1", "3", 1, {{"time", 12}});
    G.AddLink("0_2", "0", "2", 1, {{"time", 12}});
    G.AddLink("2_3", "2", "3", 1, {{"time", 12}});
    G.AddLink("0_3", "0", "3", 1, {{"time", 12}});
    G.AddLink("0_4", "0", "4", 11, {{"time", 3}});
    G.AddLink("4_3", "4", "3", 11, {{"time", 12}});

    auto paths = KShortestPath(G, "0", "3", "time", {}, 0, 10, 4);
    assertTrue(paths.size()==3, "Did not found 3 paths");


    assertTrue(paths[0].second==12, "First path cost not equal 12");
    assertTrue(paths[0].first==std::vector<std::string>{"0", "3"}, "First path nodes not equal 0, 3");
    assertTrue(paths[1].second==24, "Second path cost not equal 24");
    assertTrue(paths[1].first==std::vector<std::string>{"0", "2", "3"}, "Second path nodes not equal 0, 2, 3");
    assertTrue(paths[2].second==26, "Third path cost not equal 26");
    assertTrue(paths[2].first==std::vector<std::string>{"0", "1", "3"}, "Third path nodes not equal 0, 1, 3");


    return 0;
}
