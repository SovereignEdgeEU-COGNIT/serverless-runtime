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

# Dynamically set the COGNIT_BROKER variable
FRONTEND_VM_ID=$(onegate service show --json | jq -r '.SERVICE.roles[] | select(.name == "Frontend").nodes[0].vm_info.VM.ID')
FRONTEND_VM_IP=$(onegate vm show "$FRONTEND_VM_ID" --json | jq -r '.VM.TEMPLATE.NIC[0].IP')
COGNIT_BROKER="amqp://rabbitadmin:rabbitadmin@${FRONTEND_VM_IP}:5672"

# Check required environment variables
if [[ -z "$COGNIT_BROKER" || -z "$COGNIT_FLAVOUR" ]]; then
  echo "COGNIT_BROKER or COGNIT_FLAVOUR is not set."
fi

cd /root/serverless-runtime/
source serverless-env/bin/activate

# Start the API with Uvicorn and save the PID
python3 app/main.py --host "0.0.0.0" --port 8000 --broker "$COGNIT_BROKER" --flavour "$COGNIT_FLAVOUR" &
echo $! > "$PID_FILE"

nohup python3 prometheus_metrics_injection.py --interval 5 &