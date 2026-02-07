#!/usr/bin/env bash
set -e
PROFILE="${PROFILE:-dev}"
BUILD_DIR="build"

cmake -S . -B "$BUILD_DIR/cmake" -DPROFILE="$PROFILE"
cmake --build "$BUILD_DIR/cmake" --verbose -j1
