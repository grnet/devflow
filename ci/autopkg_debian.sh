#!/usr/bin/env sh

TEMP=$(mktemp -d /tmp/autopkg_debian_XXXXX)

if [ -z $(git branch -a | grep " debian-develop") ]; then
  git branch debian-develop origin/debian-develop
fi

devflow-autopkg -b $TEMP snapshot
