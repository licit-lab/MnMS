#include "mgraph/graph.h"

#include <unordered_map>
#include <string>




std::unordered_map<std::string, double> makeSimpleCostMap(double linkLength) {
    std::unordered_map<std::string, double> costs;
    costs["length"] = linkLength;
    return costs;
}



OrientedGraph makeManhattan(int n, double linkLength) {
    OrientedGraph G;

    for (size_t i = 0; i < n; i++)
    {
        for (size_t j = 0; j < n; j++)
        {
            G.AddNode(std::to_string(i*n+j), i*linkLength, j*linkLength);
        }

    }

    for (size_t i = 0; i < n; i++)
    {
        for (size_t j = 0; j < n; j++)
        {
            int ind = i*n+j;

            if(j < n-1) {
                std::string upstream = std::to_string(ind);
                std::string downstream = std::to_string(ind+1);
                G.AddLink(upstream + "_" + downstream, upstream, downstream, makeSimpleCostMap(linkLength));
            }

            if(j > 0) {
                std::string upstream = std::to_string(ind);
                std::string downstream = std::to_string(ind-1);
                G.AddLink(upstream + "_" + downstream, upstream, downstream, makeSimpleCostMap(linkLength));
            }

            if(i < n - 1) {
                std::string upstream = std::to_string(ind);
                std::string downstream = std::to_string(ind+n);

                G.AddLink(upstream + "_" + downstream, upstream, downstream, makeSimpleCostMap(linkLength));
            }

            if(i > 0) {
                std::string upstream = std::to_string(ind);
                std::string downstream = std::to_string(ind-n);
                G.AddLink(upstream + "_" + downstream, upstream, downstream, makeSimpleCostMap(linkLength));
            }
        }

    }

    size_t counter = 0;
    for (size_t i = 0; i < n; i++)
    {
        std::string upstream = "WEST_"+std::to_string(i);
        std::string downstream = std::to_string(i);
        G.AddNode(upstream, -linkLength, i*linkLength);
        G.AddLink(upstream+"_"+downstream, upstream, downstream, makeSimpleCostMap(linkLength));
        G.AddLink(downstream+"_"+upstream, downstream, upstream, makeSimpleCostMap(linkLength));
    }

    counter = 0;
    for (size_t i = n*(n-1); i < n*n; i++)
    {
        std::string upstream = "EAST_"+std::to_string(counter);
        std::string downstream = std::to_string(i);
        G.AddNode(upstream, n*linkLength, counter*linkLength);
        G.AddLink(upstream+"_"+downstream, upstream, downstream, makeSimpleCostMap(linkLength));
        G.AddLink(downstream+"_"+upstream, downstream, upstream, makeSimpleCostMap(linkLength));
        counter++;
    }

    counter = 0;
    for (size_t i = n-1; i < n*n; i+=n)
    {
        std::string upstream = "NORTH_"+std::to_string(counter);
        std::string downstream = std::to_string(i);
        G.AddNode(upstream, counter*linkLength, n*linkLength);
        G.AddLink(upstream+"_"+downstream, upstream, downstream, makeSimpleCostMap(linkLength));
        G.AddLink(downstream+"_"+upstream, downstream, upstream, makeSimpleCostMap(linkLength));
        counter++;
    }

    counter = 0;
    for (size_t i = 0; i < n*n; i+=n)
    {
        std::string upstream = "SOUTH_"+std::to_string(counter);
        std::string downstream = std::to_string(i);
        G.AddNode(upstream, counter*linkLength, -linkLength);
        G.AddLink(upstream+"_"+downstream, upstream, downstream, makeSimpleCostMap(linkLength));
        G.AddLink(downstream+"_"+upstream, downstream, upstream, makeSimpleCostMap(linkLength));
        counter++;
    }

    return G;
}