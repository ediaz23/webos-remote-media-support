#!/usr/bin/env bash
set -e
PROFILE="${PROFILE:-dev}"
BUILD_DIR="build-docker"

cmake -S . -B "$BUILD_DIR" -DPROFILE="$PROFILE"
cmake --build "$BUILD_DIR" -j
