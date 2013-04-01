#!/bin/sh

nosetests  --with-coverage --cover-package=devflow --nologcapture \
           --cover-inclusive
