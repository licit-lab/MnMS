# cmake_minimum_required(VERSION 3.4...3.18)

# project(MgraphExample)

# find_package(Mgraph REQUIRED)



add_executable(ex1 ex1.cpp)
target_link_libraries(ex1 PUBLIC mgraphlib)

