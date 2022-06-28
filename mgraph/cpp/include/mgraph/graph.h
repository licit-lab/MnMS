#include <string>
#include <unordered_map>
#include <unordered_set>
#include <memory>
#include <set>
#include <vector>

#pragma once


typedef std::vector<std::string> vecstring;
typedef std::unordered_map<std::string, std::set<std::string> > mapsets;

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

    mapsets mexclude_movements;

    Node(std::string _id, double x, double y, mapsets exclude_movements = {}) {
        mid = _id.c_str();
        mposition[0] = x;
        mposition[1] = y;
        mexclude_movements = exclude_movements;
    }

    vecstring getExits(std::string predecessor = "_default") {
        vecstring res;
        for(const auto &l: madj) {
            std::string neighbor = l->mdownstream;
            if(mexclude_movements[neighbor].find(predecessor) == mexclude_movements[neighbor].end()) {
                res.push_back(neighbor);
            }
        }
        return res;
    }

    vecstring getEntrances(std::string predecessor) {
        vecstring res;
        for(const auto &l: mradj) {
            std::string neighbor = l->mdownstream;
            if(mexclude_movements[predecessor].find(neighbor) == mexclude_movements[predecessor].end()) {
                res.push_back(neighbor);
            }
        }
        return res;
    }

};


class OrientedGraph {
public:
    std::unordered_map<std::string, std::shared_ptr<Node> > mnodes;
    std::unordered_map<std::string, std::shared_ptr<Link> > mlinks;
    void AddNode(std::string _id, double x, double y);
    void AddNode(std::shared_ptr<Node> n);
    void AddLink(std::string _id, std::string _up, std::string _down, std::unordered_map<std::string, double> _costs);
    void AddLink(std::shared_ptr<Link> l);
    void ShowNodes();
    void ShowLinks();

};