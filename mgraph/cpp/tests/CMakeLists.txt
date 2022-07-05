# create the testing file and list of tests
create_test_sourcelist (Tests
  CommonCxxTests.cxx
  testGraph.cxx
  )

# add the executable
add_executable (CommonCxxTests ${Tests})
target_link_libraries(CommonCxxTests mgraphlib)

# remove the test driver source file
set (TestsToRun ${Tests})
remove (TestsToRun CommonCxxTests.cxx)

# Add all the ADD_TEST for each test
foreach (test ${TestsToRun})
  get_filename_component (TName ${test} NAME_WE)
  add_test (NAME ${TName} COMMAND CommonCxxTests ${TName})
endforeach ()