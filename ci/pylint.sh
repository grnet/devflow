#!/usr/bin/env sh

r=$(dirname $(realpath $0))/..
pylint $r/devflow
