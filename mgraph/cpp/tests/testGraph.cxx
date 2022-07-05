#include "helpers.h"

#include <mgraph/graph.h>

#include <unordered_map>
#include <set>
#include <string>
#include <memory>



int testGraph(int argc, char *argv[])
{
    OrientedGraph G;
    G.AddNode("a", 0, 0);

    std::unordered_map<std::string, std::set<std::string> > excludeMovements;
    excludeMovements["a"] = {"c"};
    G.AddNode("b", 2, 5, excludeMovements);
    
    std::shared_ptr<Node> newNode = std::make_shared<Node>("c", 12, 43);
    G.AddNode(newNode);
    

    G.AddNode("d", 435, 345);

    std::unordered_map<std::string, double> costAB;
    costAB["time"] = 234;
    G.AddLink("a_b", "a", "b", 12, costAB);
    

    std::unordered_map<std::string, double> costBC;
    costBC["time"] = 234;
    G.AddLink("b_c", "b", "c", 12, costBC);

    std::unordered_map<std::string, double> costBD;
    costBD["time"] = 234;
    G.AddLink("b_d", "b", "d", 12, costBD);

    std::vector<std::shared_ptr<Link> > exits = G.mnodes["b"]->getExits("a");

    assertTrue(exits.size()==1, "Exits does not return one link");
    assertTrue(exits[0]->mdownstream=="d", "Node should be d");



    return 0;
}
