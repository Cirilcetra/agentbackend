#!/bin/sh
# entrypoint.sh
# This script properly handles the PORT environment variable for Railway

# Start the application with a fixed port
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level debug 