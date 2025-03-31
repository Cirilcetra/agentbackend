import os
import uvicorn
from app.main import app

if __name__ == "__main__":
    # Get the port from the environment variable or use 8000 as default
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting server on port: {port}")
    
    # Run the server directly with the app instance
    uvicorn.run(app, host="0.0.0.0", port=port) 