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

pathCost dijkstra(const OrientedGraph &G, const std::string &origin, const std::string &destination, const std::string &cost, setstring accessibleLabels) {
    pathCost path;

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

    path.second = inf;
    prev[origin] = "";

    while (!pq.empty())
        {
        std::string u = pq.top().second;
        pq.pop();

        if(u==destination) {
            std::string v = prev[u];
            path.first.push_back(u);

            while(v!=origin) {
                path.first.push_back(v);
                v = prev[v];
            }

            path.first.push_back(v);
            std::reverse(path.first.begin(), path.first.end());
            path.second = dist[destination];
            return path;
        }

        for(const auto link: G.mnodes.at(u)->getExits(prev[u]))
        {
            if(accessibleLabels.empty() || accessibleLabels.find(link->mlabel) != accessibleLabels.end()) {
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
    }
    return path;
};


std::vector<pathCost> parallelDijkstra(const OrientedGraph &G, std::vector<std::string>  origins, std::vector<std::string>  destinations, std::string cost, int threadNumber, std::vector<setstring> vecAvailableLabels) {
    omp_set_num_threads(threadNumber);
    

    int nbPath = origins.size();
    std::vector<pathCost> res(nbPath);

    #pragma omp parallel for shared(res, vecAvailableLabels) schedule(dynamic) 
    for (int i = 0; i < nbPath; i++)
    {   
        if(vecAvailableLabels.empty()) {
            res[i] = dijkstra(G, origins[i], destinations[i], cost, {});
        }
        else {
            res[i] = dijkstra(G, origins[i], destinations[i], cost, vecAvailableLabels[i]);
        }
        
    }
    
    return res;
}


typedef std::unordered_map<std::string, std::unordered_map<std::string, double> > mapCosts;


void increaseCostsFromPath(OrientedGraph &G, const std::vector<std::string> &path, mapCosts &initial_costs) {

    for (size_t i = 0; i < path.size() - 1 ; i++)
    {
        Link *link = G.mnodes[path[i]]->madj[path[i+1]];
        if(initial_costs.find(link->mid) == initial_costs.end()) {
            for(auto &keyVal: link->mcosts) {
                initial_costs[link->mid][keyVal.first] = keyVal.second;
                keyVal.second *= 10;
            }
        }
        else {
            for(auto &keyVal: link->mcosts) {
                keyVal.second *= 10;
            }
        }
        
        
    }
    
}


double computePathLength(OrientedGraph &G, const std::vector<std::string> &path) {
    double length = 0;

    for (size_t i = 0; i < path.size() - 1 ; i++)
    {
        Link *link = G.mnodes[path[i]]->madj[path[i+1]];
        length += link->mlength;
    }

    return length;
}


double computePathCost(OrientedGraph &G, const std::vector<std::string> &path, std::string cost) {
    double c = 0;

    for (size_t i = 0; i < path.size() - 1 ; i++)
    {
        Link *link = G.mnodes[path[i]]->madj[path[i+1]];
        c += link->mcosts[cost];
        // std::cout<<link->mcosts[cost]<<std::endl;
    }

    return c; 

}


void showPath(pathCost path) {
    std::cout<< path.second << " [";
    for(const auto &p: path.first) {
        std::cout << p << ", ";
    }
    std::cout<< "]"<<std::endl;
}


std::vector<pathCost> KShortestPath(OrientedGraph &G, const std::string &origin, const std::string &destination, const std::string &cost, setstring accessibleLabels, double minDist, double maxDist, int kPath) {
    std::vector<pathCost> paths;
    mapCosts initial_costs;

    pathCost firstPath = dijkstra(G, origin, destination, cost);
    paths.push_back(firstPath);

    if(firstPath.first.empty()) {
        return paths;
    }

    // std::cout << "First path: ";
    // showPath(firstPath); 

    double firstPathLength = computePathLength(G, firstPath.first);
    
    increaseCostsFromPath(G, firstPath.first, initial_costs);

    int pathCounter=1, retry=0;

    while (pathCounter < kPath && retry < 10)
    {
        pathCost newPath = dijkstra(G, origin, destination, cost);
        // std::cout << "Computed path: ";
        // showPath(newPath); 

        increaseCostsFromPath(G, newPath.first, initial_costs);
        double newPathLength = computePathLength(G, newPath.first);

        double diffPathLength = newPathLength - firstPathLength;

        if(minDist <= diffPathLength && diffPathLength <= maxDist) {
            bool isNew = true;
            for(const auto &p: paths) {
                if(p.first == newPath.first) {
                    isNew = false;
                    break;
                }
            }

            if(isNew) {
                // std::cout<< minDist << " " << diffPathLength << " " << maxDist<<std::endl;
                // std::cout << "Accepted path: ";
                // showPath(newPath); 
                paths.push_back(newPath);
                retry = 0;
                pathCounter += 1;
            }
            else {
                retry += 1;
            }

        }

        else {
            retry += 1;
        }
    }

    
    for(const auto &keyVal: initial_costs) {
        G.mlinks[keyVal.first]->mcosts = keyVal.second;
    }

    for(auto &p:paths) {
        // showPath(p);
        p.second = computePathCost(G, p.first, cost);
        // showPath(p);
    }
    // showPath(firstPath); 

    return paths;
}



std::vector<pathCost> YenKShortestPath(OrientedGraph &G, std::string origin, std::string destination, std::string cost, setstring accessibleLabels, int kPath) {
    std::vector<pathCost> A;
    std::vector<pathCost> B;
    A.push_back(dijkstra(G, origin, destination, cost, accessibleLabels));
    std::cout << "First path: ";
    showPath(A[0]); 

    double inf = std::numeric_limits<double>::infinity();

    for (size_t k = 1; k < kPath; k++)
    {   

        std::cout<<"k="<<k<<std::endl;
        for (size_t i = 0; i < A[k-1].first.size()-2; i++)
        {
            std::cout<<"i="<<i<<std::endl;
            std::unordered_map<std::string, double> initial_costs;
            std::string spurNode = A[k-1].first[i];
            pathCost rootPath;
            rootPath.second = 0;
            rootPath.first.insert(rootPath.first.begin(), A[k-1].first.begin(), A[k-1].first.begin()+i+1);
            std::cout << "Root path: ";
            showPath(rootPath);

            if(rootPath.first.size() >= 2) {
                for (int j = 0; j < rootPath.first.size()-1; j++) {   
                    std::cout<<"Getting cost "<<G.mnodes[rootPath.first[j]]->madj[rootPath.first[j+1]]<<std::endl;
                    rootPath.second += G.mnodes[rootPath.first[j]]->madj[rootPath.first[j+1]]->mcosts[cost];
                }
            }

            for(const pathCost &pc: A) {
                std::cout << "Compare path: "<<std::endl;
                showPath(pc);
                showPath(rootPath);
                if (std::equal(pc.first.begin(), pc.first.begin()+i, rootPath.first.begin()))
                {
                    std::cout<<"Removing "<<pc.first[i]<<"->"<< pc.first[i+1]<<std::endl;
                    Link *l = G.mnodes[pc.first[i]]->madj[pc.first[i+1]];
                    
                    if(initial_costs.find(l->mid) == initial_costs.end()) {
                        initial_costs[l->mid] = l->mcosts[cost];
                    }
                    l->mcosts[cost] = inf;
                }
                
            }
            

            std::cout<<"Finish removing"<<std::endl;



            pathCost spurPath = dijkstra(G, spurNode, destination, cost, accessibleLabels);
            pathCost totalPath;
            totalPath.first = rootPath.first;

            // if(rootPath.first.size()>= 2) {
            //     totalPath.first = rootPath.first;
            // }
            
            totalPath.first.insert(totalPath.first.end(), spurPath.first.begin()+1, spurPath.first.end());
            totalPath.second = rootPath.second + spurPath.second;

            std::cout << "Full B path: ";
            showPath(totalPath); 


            for(const auto &keyVal:initial_costs) {
                std::cout<<"Reseting cost "<<keyVal.first<<" "<<keyVal.second<<std::endl;
                G.mlinks[keyVal.first]->mcosts[cost] = keyVal.second;
                std::cout<<G.mlinks[keyVal.first]<<std::endl;
                std::cout<<G.mnodes["C"]->madj["E"]<<std::endl;
            }


            bool toAdd = true;
            for(const auto &prevPath:B) {
                if(totalPath.first==prevPath.first) {
                    toAdd = false;
                    break;
                }
            }

            if(toAdd) {
                B.push_back(totalPath);
            }

            
        }

        if(B.empty()) {
            break;
        }

        std::sort(B.begin(), B.end(), [](pathCost a, pathCost b) {return a.second < b.second; });
        A[k] = B[0];
        B.erase(B.begin());
        
    }
    


    return A;

}





std::vector<std::vector<pathCost> > parallelKShortestPath(OrientedGraph &G, const std::vector<std::string> &origins, const std::vector<std::string> &destinations, const std::string &cost, std::vector<setstring> accessibleLabels, double minDist, double maxDist, int kPath, int threadNumber) {
    int nbOD = origins.size();
    
    std::vector<std::vector<pathCost> > res(nbOD);
    std::shared_ptr<OrientedGraph> privateG;

    #pragma omp parallel shared(res, accessibleLabels, G) private(privateG)
    {   
        privateG = copyGraph(G);

        #pragma omp for
        for (int i = 0; i < nbOD; i++) {   
            if(accessibleLabels.empty()) {
                res[i] = KShortestPath(*privateG, origins[i], destinations[i], cost, {}, minDist, maxDist, kPath);
            }
            else {
                res[i] = KShortestPath(*privateG, origins[i], destinations[i], cost, accessibleLabels[i], minDist, maxDist, kPath);  
            }
        
        }
    }
    return res;

}
