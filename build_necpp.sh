#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SOURCE_DIR="$ROOT_DIR/third_party/necpp"
BUILD_DIR="$SOURCE_DIR/build"

cmake -S "$SOURCE_DIR" -B "$BUILD_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DNECPP_BUILD_TESTS=OFF
cmake --build "$BUILD_DIR" --target nec2++ -j"${JOBS:-2}"