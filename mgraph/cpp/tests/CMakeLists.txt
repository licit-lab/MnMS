# create the testing file and list of tests
create_test_sourcelist (Tests
  CommonCxxTests.cpp
  testGraph.cpp
  testDijkstra1.cpp
  testDijkstra2.cpp
  testKShortestPath.cpp
)

# add the executable
add_executable (CommonCxxTests ${Tests})
target_link_libraries(CommonCxxTests mgraphlib)
target_include_directories(CommonCxxTests PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})


# remove the test driver source file
set (TestsToRun ${Tests})
remove (TestsToRun CommonCxxTests.cpp)

# Add all the ADD_TEST for each test
foreach (test ${TestsToRun})
  get_filename_component (TName ${test} NAME_WE)
  add_test (NAME ${TName} COMMAND CommonCxxTests ${TName})
endforeach ()