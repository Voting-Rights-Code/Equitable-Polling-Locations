#!/bin/bash

# export user information to integrate with host system permissions
export UID=$(id -u)
export GID=$(id -g)

# build docker container
# docker build -t equitable_locations .
docker build -t equitable_locations  --progress=plain  . &> build.log

# deploy using compose
docker compose up -d