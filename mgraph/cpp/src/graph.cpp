#include "mgraph/graph.h"


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


void OrientedGraph::AddNode(std::string _id, double x, double y) {
    std::shared_ptr<Node> new_node = std::make_shared<Node>(_id, x, y);
    mnodes[_id] = new_node;
};

void OrientedGraph::AddNode(std::shared_ptr<Node> n) {
    mnodes[n->mid] = n;
};


void OrientedGraph::AddLink(std::string _id, std::string _up, std::string _down, std::unordered_map<std::string, double> _costs) {
    std::shared_ptr<Link> new_link = std::make_shared<Link>(_id, _up, _down, _costs);
    mnodes[_up]->madj.insert(new_link);
    mnodes[_down]->mradj.insert(new_link);

    mlinks[_id] = new_link;
};


void OrientedGraph::AddLink(std::shared_ptr<Link> l) {
    mnodes[l->mupstream]->madj.insert(l);
    mnodes[l->mdownstream]->mradj.insert(l);

    mlinks[l->mid] = l;
};




void OrientedGraph::ShowNodes() {
    for(const auto &elem: mnodes) {
        std::cout << "Node(" << elem.first << ", [" << elem.second->mposition[0] << ",\t" << elem.second->mposition[1] << "])\n";
    }
}

void OrientedGraph::ShowLinks() {
    for(const auto &elem: mlinks) {
        std::cout << "Link(" << elem.first << ", " << elem.second->mupstream << ", " << elem.second->mdownstream << ")\n";
    }
}








