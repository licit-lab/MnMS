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


OrientedGraph::~OrientedGraph() {
    for (auto iter : mnodes) { 
        delete iter.second; 
    }

    for (auto iter : mlinks) { 
        delete iter.second; 
    }
}


void OrientedGraph::AddNode(std::string _id, double x, double y, std::string label, mapsets excludeMovements) {
    Node *new_node = new Node(_id, x, y, label, excludeMovements);
    mnodes[_id] = new_node;
};

void OrientedGraph::AddNode(Node* n) {
    mnodes[n->mid] = n;
};


void OrientedGraph::AddLink(std::string _id, std::string _up, std::string _down, double length, std::unordered_map<std::string, double> _costs, std::string label) {
    Link *new_link = new Link(_id, _up, _down, length, _costs, label);
    mnodes[_up]->madj[_down] = new_link;
    mnodes[_down]->mradj[_up] = new_link;

    mlinks[_id] = new_link;
};


void OrientedGraph::AddLink(Link *l) {
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
        Node *n = new Node(*keyVal.second);

        newGraph->AddNode(n);
    }


    for(const auto &keyVal: G.mlinks) {
        Link *l = new Link(*keyVal.second);
        newGraph->AddLink(l);

    }



    return newGraph;
}



std::shared_ptr<OrientedGraph> mergeOrientedGraph(std::vector<std::shared_ptr<OrientedGraph> > allGraphs){
    std::shared_ptr<OrientedGraph> newGraph = std::make_shared<OrientedGraph>();

    for(auto G:allGraphs) {
        for(const auto &keyValNodes:G->mnodes) {
            mapsets excludeMovements;
            for(const auto &keyVal: keyValNodes.second->mexclude_movements) {
                setstring copy;
                for(const auto &s: keyVal.second) {
                    copy.insert(s.c_str());
                }
                excludeMovements[keyVal.first] = copy;
            }
            newGraph->AddNode(keyValNodes.first, keyValNodes.second->mposition[0], keyValNodes.second->mposition[1], keyValNodes.second->mlabel, excludeMovements);
        }

        for(const auto &keyVal: G->mlinks) {
            std::unordered_map<std::string, double> costs;

            for(const auto &keyVal: keyVal.second->mcosts) {
                costs[keyVal.first] = keyVal.second;
            }

            newGraph->AddLink(keyVal.first, 
                    keyVal.second->mupstream,
                    keyVal.second->mdownstream,
                    keyVal.second->mlength,
                    costs,
                    keyVal.second->mlabel);

        }
    }



    return newGraph;
}
