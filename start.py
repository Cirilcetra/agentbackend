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
    
    # Debug all environment variables to see what's available
    logger.info("All environment variables (keys only):")
    env_keys = list(os.environ.keys())
    logger.info(f"Found {len(env_keys)} environment variables: {', '.join(env_keys)}")
    
    # Detailed check of critical variables
    for var in env_vars:
        # Check using os.environ.get
        env_value = os.environ.get(var)
        # Check using os.getenv
        getenv_value = os.getenv(var)
        
        if env_value or getenv_value:
            # Mask sensitive values
            value = env_value or getenv_value
            
            # Show which method found the value
            source = []
            if env_value: source.append("os.environ")
            if getenv_value: source.append("os.getenv")
            
            if var in ["OPENAI_API_KEY", "SUPABASE_KEY", "DATABASE_URL"]:
                masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "****"
                logger.info(f"✓ {var}: {masked} (found via {', '.join(source)})")
            else:
                logger.info(f"✓ {var}: {value} (found via {', '.join(source)})")
        else:
            logger.warning(f"✗ {var}: Not set")
    
    # Special focus on OpenAI API key
    openai_key = os.environ.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.error("❌ OPENAI_API_KEY not found in environment variables!")
        return False
    logger.info("✓ OPENAI_API_KEY found")
    return True

def start_server():
    """Start the uvicorn server with proper port handling"""
    try:
        # Check environment
        check_environment()
        
        # Get PORT from environment variable with fallback to 8080
        port = os.environ.get("PORT", "8080")
        
        # Ensure PORT is an integer
        try:
            port = int(port)
        except ValueError:
            logger.warning(f"Invalid PORT value: {port}, using default 8080")
            port = 8080
        
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