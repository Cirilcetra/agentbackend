#!/bin/bash

# Print debug information
echo "Environment variables:"
env

# Set default port if not provided
PORT="${PORT:-8080}"
echo "Using port: $PORT"

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" 