cmake_minimum_required(VERSION 3.19)
project(Mgraph VERSION 1.0.0)



# set(OpenMP_DIR ${CMAKE_PREFIX_PATH}/include)
find_package(OpenMP REQUIRED)

# set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fopenmp")

set(MGRAPH_HEADERS
  include/mgraph/create.h
  include/mgraph/graph.h
  include/mgraph/shortest_path.h
)
message(STATUS "OPENMP DIRS: ${OpenMP_CXX_INCLUDE_DIRS}")


add_subdirectory(src)



# ------------- TESTS -------------

include(CTest)
add_subdirectory(tests)


# ---------------------------------







install(DIRECTORY include/
    DESTINATION ${CMAKE_INSTALL_PREFIX}/include
    FILES_MATCHING PATTERN "*.h"
    PATTERN "*_p.h" EXCLUDE
)


install(TARGETS mgraphlib
        EXPORT MgraphTarget
        RUNTIME DESTINATION ${CMAKE_INSTALL_PREFIX}/bin COMPONENT RuntimeExecutables
        LIBRARY DESTINATION ${CMAKE_INSTALL_PREFIX}/lib COMPONENT RuntimeLibraries
        ARCHIVE DESTINATION ${CMAKE_INSTALL_PREFIX}/lib COMPONENT Development
        PUBLIC_HEADER DESTINATION ${CMAKE_INSTALL_PREFIX}/include/mgraph
)


install(EXPORT MgraphTarget DESTINATION ${CMAKE_INSTALL_PREFIX}/lib/cmake/mgraph)

include(CMakePackageConfigHelpers)
write_basic_package_version_file(${CMAKE_BINARY_DIR}/Mgraph/MgraphConfigVersion.cmake
  VERSION ${Mgraph_VERSION}
  COMPATIBILITY ExactVersion)

configure_package_config_file(${Mgraph_SOURCE_DIR}/cmake/MgraphConfig.cmake.in
${CMAKE_BINARY_DIR}/Mgraph/MgraphConfig.cmake
INSTALL_DESTINATION ${CMAKE_INSTALL_PREFIX}/lib/cmake/mgraph)

install(
  FILES
  ${CMAKE_BINARY_DIR}/Mgraph/MgraphConfig.cmake
  ${CMAKE_BINARY_DIR}/Mgraph/MgraphConfigVersion.cmake
  DESTINATION ${CMAKE_INSTALL_PREFIX}/lib/cmake/mgraph
  COMPONENT Development)