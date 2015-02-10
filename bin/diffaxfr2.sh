#!/bin/bash

set -o errexit

python -m bin.lib.diffaxfr2 $*
