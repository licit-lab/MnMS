#include "mgraph/graph.h"
#include "mgraph/shortest_path.h"


#include <vector>
#include <queue>
#include <unordered_map>
#include <string>
#include <numeric>
#include <limits>
#include <algorithm>
#include <omp.h>

#include <iostream>




typedef std::pair<double, std::string> QueueItem;
typedef std::priority_queue< QueueItem, std::vector<QueueItem> , std::greater<QueueItem> > PriorityQueue;

std::vector<std::string> dijkstra(const OrientedGraph &G, const std::string &origin, const std::string &destination, const std::string &cost) {
    std::vector<std::string> path;

    PriorityQueue pq;

    std::unordered_map<std::string, double> dist;
    std::unordered_map<std::string, std::string> prev;
    prev.reserve(G.mnodes.size());
    dist.reserve(G.mnodes.size());
    double inf = std::numeric_limits<double>::infinity();
    for (const auto keyVal : G.mnodes) {
        dist[keyVal.first] = inf;
    }
    pq.push(make_pair(0, origin));
    dist[origin] = 0;

    while (!pq.empty())
        {
        std::string u = pq.top().second;
        pq.pop();

        if(u==destination) {
            std::string v = prev[u];
            path.push_back(u);

            while(v!=origin) {
                path.push_back(v);
                v = prev[v];
            }

            path.push_back(v);
            std::reverse(path.begin(), path.end());
            return path;
        }

        for(const auto link: G.mnodes.at(u)->madj)
        {
            std::string neighbor = link->mdownstream;
            double new_dist = dist[u] + link->mcosts[cost];

            if (dist[neighbor] > new_dist)
            {
                dist[neighbor] = new_dist;
                pq.push(QueueItem(new_dist, neighbor));
                prev[neighbor] = u;
            }
        }
    }
    return path;
};


std::vector<std::vector<std::string>> parallelDijkstra(const OrientedGraph &G, std::vector<std::string>  origins, std::vector<std::string>  destinations, std::string cost, int threadNumber) {
    omp_set_num_threads(threadNumber);

    int nbPath = origins.size();
    std::vector<std::vector<std::string>> res(nbPath);

    #pragma omp parallel for shared(res) schedule(dynamic) 
    for (size_t i = 0; i < nbPath; i++)
    {
        // std::cout << "Current thread number: " << omp_get_thread_num() << std::endl;
        res[i] = dijkstra(G, origins[i], destinations[i], cost);
    }
    
    return res;
}
