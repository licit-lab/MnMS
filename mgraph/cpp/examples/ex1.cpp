#include <mgraph/create.h>
#include <mgraph/graph.h>
#include <mgraph/shortest_path.h>

#include <iostream>


int main(int argc, char const *argv[])
{
    OrientedGraph G = makeManhattan(100, 100);
    
    std::vector<std::string> path = dijkstra(G, "NORTH_0", "EAST_0", "length");
    
    int nPaths = 3000;

    std::vector<std::string>  origins(nPaths);
    std::vector<std::string>  destinations(nPaths);

    std::vector<std::vector<std::string>> paths(nPaths);
    
    for (size_t i = 0; i < nPaths; i++)
    {
        origins[i] = "NORTH_0";
        destinations[i] = "EAST_0"; 
    }
    

    paths = parallelDijkstra(G, origins, destinations, "length", 8);


    return 0;
}
