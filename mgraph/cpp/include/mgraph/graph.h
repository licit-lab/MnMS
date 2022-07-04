#include <string>
#include <unordered_map>
#include <unordered_set>
#include <memory>
#include <set>
#include <vector>

#include <iostream>

#pragma once

typedef std::set<std::string> setstring;
typedef std::vector<std::string> vecstring;
typedef std::unordered_map<std::string, std::set<std::string> > mapsets;

class Link{
public:
    std::string mid;
    std::string mupstream;
    std::string mdownstream;
    std::unordered_map<std::string, double> mcosts;
    std::string mlabel;
    double mlength;

    Link(std::string _id, std::string _up, std::string _down, double length, std::unordered_map<std::string, double> _costs, std::string label = "_def") {
        mid = _id.c_str();
        mlabel = label.c_str();
        mupstream = _up.c_str();
        mdownstream = _down.c_str();
        mcosts = _costs;
        mlength = length;
    }

    Link(const Link &other) {
        mid = other.mid.c_str();
        mlabel = other.mlabel.c_str();
        mupstream = other.mupstream.c_str();
        mdownstream = other.mdownstream.c_str();
        mlength = other.mlength;

        for(const auto &keyVal: other.mcosts) {
            mcosts[keyVal.first] = keyVal.second;
        }


    }

    void updateCosts(std::unordered_map<std::string, double> costs) {
        for(const auto &keyVal: costs) {
            mcosts[keyVal.first] = keyVal.second;
        }
    }
};


class Node {
public:
    std::string mid;
    double mposition[2];
    std::unordered_map<std::string, std::shared_ptr<Link> > madj;
    std::unordered_map<std::string, std::shared_ptr<Link> > mradj;

    mapsets mexclude_movements;

    Node(std::string _id, double x, double y, mapsets exclude_movements = {}) {
        mid = _id.c_str();
        mposition[0] = x;
        mposition[1] = y;
        mexclude_movements = exclude_movements;
    }

    Node(const Node &other) {
        mid = other.mid.c_str();
        mposition[0] = other.mposition[0];
        mposition[1] = other.mposition[1];

        for(const auto &keyVal: other.madj) {
            madj[keyVal.first] = keyVal.second;
        }

        for(const auto &keyVal: other.mradj) {
            mradj[keyVal.first] = keyVal.second;
        }

        for(const auto &keyVal: other.mexclude_movements) {
            setstring copy;
            for(const auto &s: keyVal.second) {
                copy.insert(s.c_str());
            }

            mexclude_movements[keyVal.first] = copy;
        }
    } 

    std::vector<std::shared_ptr<Link> > getExits(std::string predecessor = "_default") {
        std::vector<std::shared_ptr<Link> > res;
        for(const auto &l: madj) {
            std::string neighbor = l.second->mdownstream;
            if(mexclude_movements.find(predecessor) == mexclude_movements.end() || mexclude_movements[neighbor].find(predecessor) == mexclude_movements[neighbor].end()) {
                res.push_back(l.second);
            }
        }
        return res;
    }

    std::vector<std::shared_ptr<Link> > getEntrances(std::string predecessor) {
        std::vector<std::shared_ptr<Link> > res;
        for(const auto &l: mradj) {
            std::string neighbor = l.second->mupstream;
            if(mexclude_movements[predecessor].find(neighbor) == mexclude_movements[predecessor].end()) {
                res.push_back(l.second);
            }
        }
        return res;
    }

};


class OrientedGraph {
public:
    std::unordered_map<std::string, std::shared_ptr<Node> > mnodes;
    std::unordered_map<std::string, std::shared_ptr<Link> > mlinks;
    void AddNode(std::string _id, double x, double y, mapsets excludeMovements = {});
    void AddNode(std::shared_ptr<Node> n);
    void AddLink(std::string _id, std::string _up, std::string _down, double length, std::unordered_map<std::string, double> _costs);
    void AddLink(std::shared_ptr<Link> l);
    void ShowNodes();
    void ShowLinks();

    std::shared_ptr<Link> getLink(std::string  _id) {
        return mlinks[_id];
    }

    OrientedGraph() {};

    OrientedGraph(const OrientedGraph &other) {
        for(const auto &keyVal: other.mnodes) {
            std::shared_ptr<Node> newNode = std::make_shared<Node>(*keyVal.second);
            mnodes[keyVal.first] = newNode;
        }

        for(const auto &keyVal: other.mlinks) {
            std::shared_ptr<Link> newLink = std::make_shared<Link>(*keyVal.second);
            mlinks[keyVal.first] = newLink;
        }
    }

};


std::shared_ptr<OrientedGraph> copyGraph(const OrientedGraph &G);