#!/usr/bin/env sh

if [ -z $(git branch -a | grep " debian-develop") ]; then
  git branch debian-develop origin/debian-develop
fi

devflow-autopkg -b $1 snapshot
