cmake_minimum_required(VERSION 3.17)

project(concretecompiler LANGUAGES C CXX)

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Needed on linux with clang 15 and on MacOS because cxx emits dollars in the optimizer C++ API
add_definitions("-Wno-dollar-in-identifier-extension")

add_definitions("-Wall ")
add_definitions("-Werror ")
add_definitions("-Wfatal-errors")

# If we are trying to build the compiler with LLVM/MLIR as libraries
if(NOT DEFINED LLVM_EXTERNAL_CONCRETELANG_SOURCE_DIR)
  message(FATAL_ERROR "Concrete compiler requires a unified build with LLVM/MLIR")
endif()

# CMake library generation settings.
set(BUILD_SHARED_LIBS
    OFF
    CACHE BOOL "Default to building a static mondo-lib")
set(CMAKE_PLATFORM_NO_VERSIONED_SONAME
    ON
    CACHE BOOL "Python soname linked libraries are bad")
set(CMAKE_VISIBILITY_INLINES_HIDDEN
    ON
    CACHE BOOL "Hide inlines")

# The -fvisibility=hidden option only works for static builds.
if(BUILD_SHARED_LIBS AND (CMAKE_CXX_VISIBILITY_PRESET STREQUAL "hidden"))
  message(FATAL_ERROR "CMAKE_CXX_VISIBILITY_PRESET=hidden is incompatible \
                        with BUILD_SHARED_LIBS.")
endif()

set(MLIR_MAIN_SRC_DIR ${LLVM_MAIN_SRC_DIR}/../mlir) # --src-root
set(MLIR_INCLUDE_DIR ${MLIR_MAIN_SRC_DIR}/include) # --includedir
set(MLIR_TABLEGEN_OUTPUT_DIR ${LLVM_BINARY_DIR}/tools/mlir/include)
set(MLIR_TABLEGEN_EXE $<TARGET_FILE:mlir-tblgen>)
include_directories(SYSTEM ${MLIR_INCLUDE_DIR})
include_directories(SYSTEM ${MLIR_TABLEGEN_OUTPUT_DIR})

list(APPEND CMAKE_MODULE_PATH "${MLIR_MAIN_SRC_DIR}/cmake/modules")

include_directories(${PROJECT_SOURCE_DIR}/include)
include_directories(${PROJECT_BINARY_DIR}/include)
link_directories(${LLVM_BUILD_LIBRARY_DIR})
add_definitions(${LLVM_DEFINITIONS})

# Custom doc generation function
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake/modules")
include(AddConcretelangDoc)
set(CONCRETELANG_BINARY_DIR ${CMAKE_CURRENT_BINARY_DIR})

# -------------------------------------------------------------------------------
# Concrete Security curves Configuration
# -------------------------------------------------------------------------------
include_directories(${PROJECT_SOURCE_DIR}/../../../tools/parameter-curves/concrete-security-curves-cpp/include)

# -------------------------------------------------------------------------------
# Concrete Optimizer
# -------------------------------------------------------------------------------

set(CONCRETE_OPTIMIZER_DIR "${PROJECT_SOURCE_DIR}/../../concrete-optimizer")
set(CONCRETE_OPTIMIZER_RELEASE_DIR "${CONCRETE_OPTIMIZER_DIR}/target/release")
set(CONCRETE_OPTIMIZER_INCLUDE_DIR "${CONCRETE_OPTIMIZER_DIR}/concrete-optimizer-cpp/src/cpp")
set(CONCRETE_OPTIMIZER_STATIC_LIB "${CONCRETE_OPTIMIZER_RELEASE_DIR}/libconcrete_optimizer_cpp.a")

ExternalProject_Add(
  concrete_optimizer_rust
  DOWNLOAD_COMMAND ""
  CONFIGURE_COMMAND "" OUTPUT "${CONCRETE_OPTIMIZER_STATIC_LIB}"
  BUILD_ALWAYS true
  BUILD_COMMAND cargo build -p concrete-optimizer-cpp --profile release
  BINARY_DIR "${CONCRETE_OPTIMIZER_DIR}"
  INSTALL_COMMAND ""
  LOG_BUILD ON
  LOG_OUTPUT_ON_FAILURE ON)

add_library(concrete_optimizer STATIC ${CONCRETE_OPTIMIZER_DIR}/concrete-optimizer-cpp/src/cpp/concrete-optimizer.cpp)

target_link_libraries(concrete_optimizer PRIVATE pthread m dl
                                                 "${CONCRETE_OPTIMIZER_DIR}/target/release/libconcrete_optimizer_cpp.a")
install(TARGETS concrete_optimizer EXPORT concrete_optimizer)
install(EXPORT concrete_optimizer DESTINATION "./")

add_dependencies(concrete_optimizer concrete_optimizer_rust)
# TODO - Remove the global include directory
include_directories(${CONCRETE_OPTIMIZER_INCLUDE_DIR})

# -------------------------------------------------------------------------------
# Concrete Backends
# -------------------------------------------------------------------------------

set(CONCRETE_BACKENDS_DIR "${PROJECT_SOURCE_DIR}/../../../backends")

# -------------------------------------------------------------------------------
# Concrete CPU Configuration
# -------------------------------------------------------------------------------

set(CONCRETE_CPU_DIR "${CONCRETE_BACKENDS_DIR}/concrete-cpu/implementation")
set(CONCRETE_CPU_RELEASE_DIR "${CONCRETE_CPU_DIR}/target/release")
set(CONCRETE_CPU_INCLUDE_DIR "${CONCRETE_CPU_DIR}/include")
set(CONCRETE_CPU_STATIC_LIB "${CONCRETE_CPU_RELEASE_DIR}/libconcrete_cpu.a")

if(CMAKE_HOST_SYSTEM_PROCESSOR STREQUAL "x86_64")
  set(CONCRETE_CPU_FEATURES "--features=x86_64")
elseif(CMAKE_HOST_SYSTEM_PROCESSOR STREQUAL "aarch64")
  set(CONCRETE_CPU_FEATURES "--features=aarch64")
endif()

ExternalProject_Add(
  concrete_cpu_rust
  DOWNLOAD_COMMAND ""
  CONFIGURE_COMMAND "" OUTPUT "${CONCRETE_CPU_STATIC_LIB}"
  BUILD_ALWAYS true
  BUILD_COMMAND cargo +nightly build --release ${CONCRETE_CPU_FEATURES} --features=nightly
  BINARY_DIR "${CONCRETE_CPU_DIR}"
  INSTALL_COMMAND ""
  LOG_BUILD ON
  LOG_OUTPUT_ON_FAILURE ON)

add_library(concrete_cpu STATIC IMPORTED)
set_target_properties(concrete_cpu PROPERTIES IMPORTED_LOCATION "${CONCRETE_CPU_STATIC_LIB}")
add_dependencies(concrete_cpu concrete_cpu_rust)

# --------------------------------------------------------------------------------
# Concrete Cuda Configuration
# --------------------------------------------------------------------------------
option(CONCRETELANG_CUDA_SUPPORT "Support Concrete CUDA Execution." OFF)

set(CONCRETE_CUDA_DIR "${CONCRETE_BACKENDS_DIR}/concrete-cuda/implementation")

if(CONCRETELANG_CUDA_SUPPORT)
  remove_definitions("-Werror ")
  message(STATUS "Building with Concrete CUDA execution support")
  find_package(CUDAToolkit REQUIRED)
  message(STATUS "Found CUDA version: ${CUDAToolkit_VERSION}")
  message(STATUS "Found CUDA library dir: ${CUDAToolkit_LIBRARY_DIR}")
  link_directories(${CUDAToolkit_LIBRARY_DIR})
  set(CONCRETE_CUDA_BUILD_TESTS OFF)
  set(CONCRETE_CUDA_BUILD_BENCHMARKS OFF)
  add_subdirectory(${CONCRETE_CUDA_DIR} concrete-cuda)
  include_directories(${CONCRETE_CUDA_DIR}/include)
  include_directories(${CUDAToolkit_INCLUDE_DIRS})
  add_compile_options(-DCONCRETELANG_CUDA_SUPPORT)
endif()

# --------------------------------------------------------------------------------
# Python Configuration
# -------------------------------------------------------------------------------
option(CONCRETELANG_BINDINGS_PYTHON_ENABLED "Enables ConcreteLang Python bindings." ON)

if(CONCRETELANG_BINDINGS_PYTHON_ENABLED)
  message(STATUS "ConcreteLang Python bindings are enabled.")

  include(MLIRDetectPythonEnv)
  mlir_configure_python_dev_packages()
  set(CONCRETELANG_PYTHON_PACKAGES_DIR ${CMAKE_CURRENT_BINARY_DIR}/python_packages)
else()
  message(STATUS "ConcreteLang Python bindings are disabled.")
endif()

# -------------------------------------------------------------------------------
# DFR - parallel execution configuration
# -------------------------------------------------------------------------------
option(CONCRETELANG_DATAFLOW_EXECUTION_ENABLED "Enables dataflow execution for ConcreteLang." ON)
option(CONCRETELANG_TIMING_ENABLED "Enables execution timing." ON)

if(CONCRETELANG_DATAFLOW_EXECUTION_ENABLED)
  message(STATUS "ConcreteLang dataflow execution enabled.")

  find_package(HPX REQUIRED CONFIG)
  list(APPEND CMAKE_MODULE_PATH "${HPX_CMAKE_DIR}")
  add_compile_options(-DCONCRETELANG_DATAFLOW_EXECUTION_ENABLED
                      -DHPX_DEFAULT_CONFIG_FILE="${PROJECT_SOURCE_DIR}/hpx.ini")

else()
  message(STATUS "ConcreteLang dataflow execution disabled.")
endif()

if(CONCRETELANG_TIMING_ENABLED)
  add_compile_options(-DCONCRETELANG_TIMING_ENABLED)
else()
  message(STATUS "ConcreteLang execution timing disabled.")
endif()

# -------------------------------------------------------------------------------
# Unit tests
# -------------------------------------------------------------------------------
option(CONCRETELANG_UNIT_TESTS "Enables the build of unittests" ON)
option(
  CONCRETELANG_UNSECURE_DEBUG
  "Totally unsecure mode where secret keys are filled with zeros. Useful to reveal the body of the ciphertexts when using tracing during debug."
  OFF)
if(CONCRETELANG_UNSECURE_DEBUG)
  message(
    WARNING
      "
  #############################################################################
  ##                                                                         ##
  ##                            !!! WARNING !!!                              ##
  ##                                                                         ##
  ##  CONCRETELANG_UNSECURE_DEBUG option activated ! This means that the     ##
  ##  secret keys generated will provide ZERO security. This should only be  ##
  ##  used for debugging purpose, and NEVER in a production environment.     ##
  ##                                                                         ##
  #############################################################################
  ")
  add_compile_definitions(CONCRETELANG_GENERATE_UNSECURE_SECRET_KEYS)
  add_compile_definitions(CONCRETELANG_TEST_KEYCACHE_PATH="UnsecureKeySetCache")
endif()

# -------------------------------------------------------------------------------
# Benchmarks
# -------------------------------------------------------------------------------
option(CONCRETELANG_BENCHMARK "Enables the build of benchmarks" ON)

# -------------------------------------------------------------------------------
# Handling sub dirs
# -------------------------------------------------------------------------------

add_subdirectory(include)
add_subdirectory(lib)
add_subdirectory(src)
add_subdirectory(tests)
