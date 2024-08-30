#!/bin/bash
# see uvicorn documentaion https://www.uvicorn.org/deployment/
# Note the timeout here may override any timeout specified in optimization tasks
gunicorn -w 2 -k uvicorn.workers.UvicornH11Worker equitable_locations.api_main:app --timeout 36000 --keep-alive 30 -b 0.0.0.0:8000