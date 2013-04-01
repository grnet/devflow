#!/bin/sh

r=$(dirname $(realpath $0))/..
pep8 $r/devflow
