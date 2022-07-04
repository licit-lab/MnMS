set(MGRAPH_SRC
  create.cpp
  graph.cpp
  shortest_path.cpp
)

add_library(mgraphlib ${MGRAPH_SRC})

target_link_libraries(mgraphlib PUBLIC OpenMP::OpenMP_CXX)

set_property(TARGET mgraphlib PROPERTY CXX_STANDARD 17)

target_include_directories( mgraphlib PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/../include>
    $<INSTALL_INTERFACE:include>
)