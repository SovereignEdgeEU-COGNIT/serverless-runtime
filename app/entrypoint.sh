#!/bin/bash

# Kill existing Uvicorn process if running
[ -f uvicorn.pid ] && kill $(cat uvicorn.pid) 2>/dev/null && echo "Previous process killed" || echo "No running process to kill"

# Source the one_env file to load variables
source /var/run/one-context/one_env

# Get the COGNIT_BROKER and COGNIT_FLAVOUR from env, or fail if not set
if [[ -z "$COGNIT_BROKER" || -z "$COGNIT_FLAVOUR" ]]; then
  echo "COGNIT_BROKER or COGNIT_FLAVOUR is not set. Aborting."
  exit 1
fi

# Start the API with Uvicorn
cd app/
python3 main.py --host "0.0.0.0" --port 8000 --broker "$COGNIT_BROKER" --flavour "$COGNIT_FLAVOUR" & echo $! > ../uvicorn.pid
