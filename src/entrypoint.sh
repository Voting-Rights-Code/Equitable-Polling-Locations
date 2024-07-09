#!/bin/bash
# see uvicorn documentaion https://www.uvicorn.org/deployment/
gunicorn -w 1 -k uvicorn.workers.UvicornH11Worker equitable_locations.api_main:app -b 0.0.0.0:8000