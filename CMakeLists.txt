cmake_minimum_required(VERSION 4.2)
project(Gum)

set(CMAKE_CXX_STANDARD 20)

include_directories(.)
include_directories(Gum)
include_directories(Gum/templates)

add_executable(Gum
        main.cpp
        Gum/templates/gum-builtins.hpp)
