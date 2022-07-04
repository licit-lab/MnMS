cmake_minimum_required(VERSION 3.4...3.18)
project(pymgraph)

find_package(pybind11 REQUIRED)
find_package(OpenMP REQUIRED)

pybind11_add_module(cpp mgraph/cpp/main.cpp)
set_target_properties(cpp PROPERTIES CXX_STANDARD 17)

find_package(Mgraph REQUIRED)
target_link_libraries(cpp PUBLIC mgraphlib)