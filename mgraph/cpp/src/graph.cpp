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


void OrientedGraph::AddNode(std::string _id, double x, double y, mapsets excludeMovements) {
    std::shared_ptr<Node> new_node = std::make_shared<Node>(_id, x, y,excludeMovements);
    mnodes[_id] = new_node;
};

void OrientedGraph::AddNode(std::shared_ptr<Node> n) {
    mnodes[n->mid] = n;
};


void OrientedGraph::AddLink(std::string _id, std::string _up, std::string _down, double length, std::unordered_map<std::string, double> _costs) {
    std::shared_ptr<Link> new_link = std::make_shared<Link>(_id, _up, _down, length, _costs);
    mnodes[_up]->madj[_down] = new_link;
    mnodes[_down]->mradj[_up] = new_link;

    mlinks[_id] = new_link;
};


void OrientedGraph::AddLink(std::shared_ptr<Link> l) {
    mnodes[l->mupstream]->madj[l->mdownstream] = l;
    mnodes[l->mdownstream]->mradj[l->mupstream] = l;

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



std::shared_ptr<OrientedGraph> copyGraph(const OrientedGraph &G) {
    std::shared_ptr<OrientedGraph> newGraph = std::make_shared<OrientedGraph>();

    for(const auto &keyVal: G.mnodes) {
        mapsets excludeMovements;

        for(const auto &keyValExclude: keyVal.second->mexclude_movements) {
            excludeMovements[keyValExclude.first] = setstring(keyValExclude.second);
        }

        newGraph->AddNode(keyVal.second->mid, keyVal.second->mposition[0], keyVal.second->mposition[1], excludeMovements);
    }


    for(const auto &keyVal: G.mlinks) {
        std::unordered_map<std::string, double> costs;

        for(const auto &keyValCosts: keyVal.second->mcosts) {
            costs[keyValCosts.first] = keyValCosts.second;
        }

        newGraph->AddLink(keyVal.second->mid,
                          keyVal.second->mupstream,
                          keyVal.second->mdownstream,
                          keyVal.second->mlength,
                          costs);

    }



    return newGraph;
}




