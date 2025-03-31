#!/bin/sh
# entrypoint.sh
# This script properly handles the PORT environment variable for Railway

# Set default port if not provided
PORT=${PORT:-8000}

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --log-level debug 