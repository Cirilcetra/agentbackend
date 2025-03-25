#!/usr/bin/env python3
"""
Railway deployment startup script
"""
import os
import sys
import subprocess
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def start_server():
    """Start the uvicorn server with proper port handling"""
    try:
        # Get PORT from environment variable with fallback to 8000
        port = os.environ.get("PORT", "8000")
        
        # Ensure PORT is an integer
        try:
            port = int(port)
        except ValueError:
            logger.warning(f"Invalid PORT value: {port}, using default 8000")
            port = 8000
        
        logger.info(f"Starting server on port {port}")
        
        # Build the command
        cmd = [
            "uvicorn", 
            "app.main:app", 
            "--host", "0.0.0.0", 
            "--port", str(port),
            "--workers", "1"
        ]
        
        # Start the server
        logger.info(f"Running command: {' '.join(cmd)}")
        subprocess.run(cmd)
        
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_server() 