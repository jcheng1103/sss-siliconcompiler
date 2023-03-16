#!/bin/sh

set -e

mkdir -p deps
cd deps

git clone https://github.com/LNIS-Projects/OpenFPGA.git
cd OpenFPGA
make all -j
cd -
