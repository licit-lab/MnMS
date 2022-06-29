#include "mgraph/graph.h"

#include <vector>
#include <string>

#include <omp.h>

#pragma once

typedef std::set<std::string> setstring;

std::vector<std::string> dijkstra(const OrientedGraph &G, const std::string &origin, const std::string &destination, const std::string &cost, setstring accessibleLabels = {});

std::vector<std::vector<std::string>> parallelDijkstra(const OrientedGraph &G, std::vector<std::string>  origins, std::vector<std::string>  destinations, std::string cost, std::vector<setstring> vecAvailableLabels = {}, int threadNumber = omp_get_max_threads());
