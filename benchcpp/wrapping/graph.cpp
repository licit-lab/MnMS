#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <memory>
#include <algorithm>
#include <queue>
#include <numeric>
#include <limits>


#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;


class Link {
public:
    std::string mid;
    std::string mupstream;
    std::string mdownstream;
    std::unordered_map<std::string, double> mcosts;

    Link(std::string _id, std::string _up, std::string _down, std::unordered_map<std::string, double> _costs) {
        mid = _id.c_str();
        mupstream = _up.c_str();
        mdownstream = _down.c_str();
        mcosts = _costs;
    }
};


class Node {
public:
    std::string mid;
    double mposition[2];
    std::unordered_set<std::shared_ptr<Link> > madj;
    std::unordered_set<std::shared_ptr<Link> > mradj;

    Node(std::string _id, double x, double y) {
        mid = _id.c_str();
        mposition[0] = x;
        mposition[1] = y;
    }
};



class OrientedGraph {
public:
    std::unordered_map<std::string, std::shared_ptr<Node> > mnodes;
    std::unordered_map<std::string, std::shared_ptr<Link> > mlinks;

    void AddNode(std::string _id, double x, double y) {
        std::shared_ptr<Node> new_node = std::make_shared<Node>(_id, x, y);
        mnodes[_id] = new_node;
    }


    void AddLink(std::string _id, std::string _up, std::string _down, std::unordered_map<std::string, double> _costs) {
        std::shared_ptr<Link> new_link = std::make_shared<Link>(_id, _up, _down, _costs);
        mnodes[_up]->madj.insert(new_link);
        mnodes[_up]->mradj.insert(new_link);

        mlinks[_id] = new_link;
    }


    void ShowNodes() {
        for(const auto &elem: mnodes) {
            std::cout << "Node(" << elem.first << ", [" << elem.second->mposition[0] << ",\t" << elem.second->mposition[1] << "])\n";
        }
    }

    void ShowLinks() {
        for(const auto &elem: mlinks) {
            std::cout << "Link(" << elem.first << ", " << elem.second->mupstream << ", " << elem.second->mdownstream << ")\n";
        }
    }

};


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


typedef std::pair<double, std::string> QueueItem;
typedef std::priority_queue< QueueItem, std::vector<QueueItem> , std::greater<QueueItem> > PriorityQueue;

std::vector<std::string> dijkstra(const OrientedGraph &G, std::string origin, std::string destination, std::string cost) {
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



PYBIND11_MODULE(cppgraph, m) {

    py::class_<Link, std::shared_ptr<Link> >(m, "Link")
          .def(py::init<std::string, std::string, std::string, std::unordered_map<std::string, double> >())
          .def_readonly("id", &Link::mid)
          .def_readonly("upstream", &Link::mupstream)
          .def_readonly("downstream", &Link::mdownstream)
          .def_readwrite("mcosts", &Link::mcosts);


    py::class_<Node, std::shared_ptr<Node> >(m, "Node")
          .def(py::init<std::string, double, double>())
          .def_readonly("id", &Node::mid)
          .def_readonly("position", &Node::mposition)
          .def_readonly("adj", &Node::madj)
          .def_readonly("radj", &Node::mradj);

    py::class_<OrientedGraph, std::shared_ptr<OrientedGraph> >(m, "OrientedGraph")
          .def(py::init<>())
          .def_readonly("nodes", &OrientedGraph::mnodes)
          .def_readonly("links", &OrientedGraph::mlinks)
          .def("add_node", &OrientedGraph::AddNode)
          .def("add_link", &OrientedGraph::AddLink);


    m.def("dijkstra", &dijkstra);

    m.def("generate_mahattan", &makeManhattan);
}