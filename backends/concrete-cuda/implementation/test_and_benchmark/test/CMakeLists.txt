find_package(CUDAToolkit)
include(FetchContent)
FetchContent_Declare(googletest
                     URL https://github.com/google/googletest/archive/03597a01ee50ed33e9dfd640b249b4be3799d395.zip)
# For Windows: Prevent overriding the parent project's compiler/linker settings
set(gtest_force_shared_crt
    ON
    CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

set(CONCRETE_CPU_BINARY_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../../concrete-cpu/implementation/target/release")
set(CONCRETE_CPU_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../../concrete-cpu/implementation")
set(CONCRETE_CUDA_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../")

if(NOT TARGET concrete_cpu)
  # Enable ExternalProject CMake module
  include(ExternalProject)

  # Add rust_example as a CMake target
  ExternalProject_Add(
    concrete_cpu
    SOURCE_DIR ${CONCRETE_CPU_SOURCE_DIR}
    DOWNLOAD_COMMAND ""
    CONFIGURE_COMMAND ""
    BUILD_COMMAND cargo build --release
    COMMAND cargo build --release
    BINARY_DIR ${CONCRETE_CPU_BINARY_DIR}
    BUILD_ALWAYS true
    INSTALL_COMMAND ""
    LOG_BUILD ON)
endif()

include_directories(${CMAKE_CURRENT_SOURCE_DIR}/../include)
include_directories(${CONCRETE_CPU_SOURCE_DIR}/include)
include_directories(${CONCRETE_CUDA_SOURCE_DIR}/include)

add_library(concrete_cpu_lib STATIC IMPORTED)
set_target_properties(concrete_cpu_lib PROPERTIES IMPORTED_LOCATION ${CONCRETE_CPU_BINARY_DIR}/libconcrete_cpu.a)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wl,--no-as-needed -ldl")

set(BINARY test_concrete_cuda)

file(
  GLOB_RECURSE TEST_SOURCES
  LIST_DIRECTORIES false
  *.h *.cpp)

set(SOURCES ${TEST_SOURCES})

add_executable(${BINARY} ${TEST_SOURCES} ../utils.cpp ../setup_and_teardown.cpp)

add_test(NAME ${BINARY} COMMAND ${BINARY})

set_target_properties(
  test_concrete_cuda
  PROPERTIES CUDA_SEPARABLE_COMPILATION ON
             CUDA_RESOLVE_DEVICE_SYMBOLS ON
             CUDA_ARCHITECTURES native)
target_link_libraries(test_concrete_cuda PUBLIC GTest::gtest_main concrete_cpu_lib concrete_cuda cudart)
find_package(CUDA REQUIRED)
include_directories("${CUDA_INCLUDE_DIRS}" "${CMAKE_CURRENT_SOURCE_DIR}")

include(GoogleTest)
gtest_discover_tests(test_concrete_cuda)
