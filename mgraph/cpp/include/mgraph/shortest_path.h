#include "mgraph/graph.h"

#include <vector>
#include <string>

#pragma once


std::vector<std::string> dijkstra(const OrientedGraph &G, const std::string &origin, const std::string &destination, const std::string &cost);

std::vector<std::vector<std::string>> parallelDijkstra(const OrientedGraph &G, std::vector<std::string>  origins, std::vector<std::string>  destinations, std::string cost, int nbThreads);
