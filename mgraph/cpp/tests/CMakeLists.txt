# create the testing file and list of tests
create_test_sourcelist (Tests
  CommonCxxTests.cxx
  testGraph.cxx
  testDijkstra1.cxx
  testDijkstra2.cxx
)

# add the executable
add_executable (CommonCxxTests ${Tests})
target_link_libraries(CommonCxxTests mgraphlib)
target_include_directories(CommonCxxTests PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})


# remove the test driver source file
set (TestsToRun ${Tests})
remove (TestsToRun CommonCxxTests.cxx)

# Add all the ADD_TEST for each test
foreach (test ${TestsToRun})
  get_filename_component (TName ${test} NAME_WE)
  add_test (NAME ${TName} COMMAND CommonCxxTests ${TName})
endforeach ()