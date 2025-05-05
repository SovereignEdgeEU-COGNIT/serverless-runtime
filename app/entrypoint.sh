#!/bin/bash

# PID file
PID_FILE="./uvicorn.pid"

# Kill existing Uvicorn process if running
if [ -f "$PID_FILE" ]; then
  kill $(cat "$PID_FILE") 2>/dev/null && echo "Previous process killed" || echo "Failed to kill previous process"
  rm -f "$PID_FILE"
else
  echo "No running process to kill"
fi

# Source the one_env file to load variables
source /var/run/one-context/one_env

# Check required environment variables
if [[ -z "$COGNIT_BROKER" || -z "$COGNIT_FLAVOUR" ]]; then
  echo "COGNIT_BROKER or COGNIT_FLAVOUR is not set."
fi

# Start the API with Uvicorn and save the PID
python3 main.py --host "0.0.0.0" --port 8000 --broker "$COGNIT_BROKER" --flavour "$COGNIT_FLAVOUR" &
echo $! > "$PID_FILE"

