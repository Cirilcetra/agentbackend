#!/bin/sh
# entrypoint.sh
# Debug information
echo "Starting application..."
echo "Working directory: $(pwd)"
echo "Directory contents: $(ls -la)"
echo "Using port: 8000"

# Start the application with a fixed port
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level debug 