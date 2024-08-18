#!/bin/bash

# permissions on log folder
chmod +t logs
touch logs/rotating-logfile.log
chmod o+w logs/rotating-logfile.log

# build docker container
# docker build -t equitable_locations .
docker build -t equitable_locations  --progress=plain  . &> build.log

# deploy using compose
docker compose up -d