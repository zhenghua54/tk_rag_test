#!/bin/bash

PID_FILE="server.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "No PID file found. Server may not be running."
    exit 1
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "Server with PID $PID stopped."
else
    echo "Process $PID not running."
fi

rm -f "$PID_FILE"
