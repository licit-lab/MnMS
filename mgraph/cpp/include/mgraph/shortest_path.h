#include "mgraph/graph.h"

#include <vector>
#include <string>
#include <utility>


#pragma once

typedef std::set<std::string> setstring;
typedef std::pair<std::vector<std::string>, double> pathCost;

pathCost dijkstra(const OrientedGraph &G, const std::string &origin, const std::string &destination, const std::string &cost, setstring accessibleLabels = {});
std::vector<pathCost> parallelDijkstra(const OrientedGraph &G, std::vector<std::string>  origins, std::vector<std::string>  destinations, std::string cost, int threadNumber, std::vector<setstring> vecAvailableLabels = {});
std::vector<pathCost> KShortestPath(OrientedGraph &G, const std::string &origin, const std::string &destination, const std::string &cost, setstring accessibleLabels, double minDist, double maxDist, int kPath);
std::vector<std::vector<pathCost> > parallelKShortestPath(OrientedGraph &G, const std::vector<std::string> &origins, const std::vector<std::string> &destinations, const std::string &cost, std::vector<setstring> accessibleLabels, double minDist, double maxDist, int kPath, int threadNumber);
std::vector<pathCost> YenKShortestPath(OrientedGraph &G, std::string origin, std::string destination, std::string cost, setstring accessibleLabels, int kPath);
