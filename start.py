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

def check_environment():
    """Check and log environment variables status"""
    # Important environment variables to check
    env_vars = [
        "OPENAI_API_KEY", 
        "SUPABASE_URL", 
        "SUPABASE_KEY",
        "PORT", 
        "RAILWAY_ENVIRONMENT",
        "DATABASE_URL"
    ]
    
    logger.info("Environment variables status:")
    for var in env_vars:
        # Check both os.environ and os.getenv for thoroughness
        value = os.environ.get(var) or os.getenv(var)
        if value:
            # Mask sensitive values
            if var in ["OPENAI_API_KEY", "SUPABASE_KEY", "DATABASE_URL"]:
                masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "****"
                logger.info(f"✓ {var}: {masked}")
            else:
                logger.info(f"✓ {var}: {value}")
        else:
            logger.warning(f"✗ {var}: Not set")

def start_server():
    """Start the uvicorn server with proper port handling"""
    try:
        # Check environment
        check_environment()
        
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