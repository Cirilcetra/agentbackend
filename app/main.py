import os
import sys
import logging
import json
from pathlib import Path

# Configure basic logging first
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables aggressively before any other imports
def load_dotenv_from_all_sources():
    """Load environment variables from all possible sources"""
    try:
        # Try to load from various dotenv files
        for env_file in ['.env', '.env.production', '.env.railway']:
            path = Path(env_file)
            if path.exists():
                logger.info(f"Loading environment variables from {env_file}")
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        try:
                            key, value = line.split('=', 1)
                            # Only set if not already in environment
                            if key not in os.environ:
                                os.environ[key] = value
                                logger.info(f"Set environment variable from {env_file}: {key}")
                        except ValueError:
                            continue
        
        # Try to load from JSON
        json_file = '.railway.secrets.json'
        if Path(json_file).exists():
            logger.info(f"Loading environment variables from {json_file}")
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    # Skip placeholder or template entries
                    if '_README' in data:
                        logger.info(f"Found placeholder .railway.secrets.json file - skipping")
                    else:
                        for key, value in data.items():
                            # Skip template values
                            if 'your-' in str(value) or 'here' in str(value):
                                logger.info(f"Skipping template value for {key}")
                                continue
                                
                            # Only set if not already in environment
                            if key not in os.environ:
                                os.environ[key] = str(value)
                                logger.info(f"Set environment variable from JSON: {key}")
            except json.JSONDecodeError:
                logger.warning(f"Could not parse {json_file} as JSON")
        
        # Log the environment variables we found
        logger.info("Environment variable check results:")
        for key in ["OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "DATABASE_URL"]:
            if key in os.environ and os.environ[key] and not 'your-' in os.environ[key]:
                # Mask the values for security
                value = os.environ[key]
                if len(value) > 8:
                    masked = value[:4] + "..." + value[-4:]
                else:
                    masked = "****"
                logger.info(f"✓ {key}: {masked}")
            else:
                logger.warning(f"✗ {key}: Not set")
        
        # Check if Railway environment variables are present
        if os.environ.get("RAILWAY_ENVIRONMENT"):
            logger.info("Running in Railway environment, expecting environment variables to be set in Railway dashboard")
    
    except Exception as e:
        logger.error(f"Error loading environment variables: {e}")

# Load environment variables before other imports
load_dotenv_from_all_sources()

# Now import the rest
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
try:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler()  # Always output to stdout for Railway
        ]
    )
    
    # Only attempt to write to log file if not in Railway environment
    if not os.getenv("RAILWAY_ENVIRONMENT"):
        try:
            logging.getLogger().addHandler(logging.FileHandler("backend.log"))
            logging.info("Added file handler for logging")
        except Exception as e:
            logging.warning(f"Could not set up file logging: {e}")
except Exception as e:
    print(f"Warning: Could not configure logging: {e}")

# Create the FastAPI app
app = FastAPI(
    title="AI Agent Backend",
    description="Backend API for AI Agent chatbot and profile management",
    version="1.0.0"
)

# Add CORS middleware
allowed_origins = os.getenv("FRONTEND_URL", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if "*" not in allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import modules with error handling
try:
    from app import models
    from app.database import get_profile_data, update_profile_data, log_chat_message, get_chat_history
    logging.info("Database modules imported successfully")
except Exception as e:
    logging.error(f"Error importing database modules: {e}")
    # Create stub functions to prevent app from crashing if database fails
    def get_profile_data(*args, **kwargs): 
        return {"bio": "Demo mode - database connection failed", "id": "demo"}
    def update_profile_data(*args, **kwargs): return {}
    def log_chat_message(*args, **kwargs): return [{"id": "demo"}]
    def get_chat_history(*args, **kwargs): return []
    # Create minimal models module if needed
    import types
    models = types.SimpleNamespace()
    models.ChatRequest = BaseModel
    models.ChatHistoryItem = BaseModel
    models.ChatHistoryResponse = BaseModel

try:
    from app.embeddings import add_profile_to_vector_db, query_vector_db, generate_ai_response, add_conversation_to_vector_db
    logging.info("Embeddings modules imported successfully")
except Exception as e:
    logging.error(f"Error importing embeddings modules: {e}")
    # Create stub functions for AI functionality
    def add_profile_to_vector_db(*args, **kwargs): return True
    def query_vector_db(*args, **kwargs): return {"documents": [], "metadatas": [], "distances": []}
    def generate_ai_response(*args, **kwargs): 
        return "AI services are currently in demo mode due to initialization errors. Please check the logs."
    def add_conversation_to_vector_db(*args, **kwargs): return True

# Try importing routes, but app can run without them
try:
    from app.routes import chatbot, profiles, admin
    # Include routers from the routes directory
    app.include_router(chatbot.router, prefix="/chat", tags=["chatbot"])
    app.include_router(profiles.router, prefix="/profile", tags=["profiles"])
    app.include_router(admin.router, prefix="/admin", tags=["admin"])
    logging.info("Route modules imported and registered successfully")
except Exception as e:
    logging.error(f"Error loading route modules: {e}")
    logging.warning("Running with limited API endpoints (core endpoints only)")

# Define models (moved below other imports)
class ProfileData(BaseModel):
    bio: Optional[str] = None
    skills: Optional[str] = None
    experience: Optional[str] = None
    projects: Optional[str] = None
    interests: Optional[str] = None
    name: Optional[str] = None
    location: Optional[str] = None

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    user_id: Optional[str] = None  # Kept for API compatibility but not used
    visitor_id: Optional[str] = None
    visitor_name: Optional[str] = None

# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint for health checks
    This is used by Railway to verify the application is running
    """
    # Simple, fast response that doesn't depend on any external services
    config = {
        "status": "healthy",
        "service": "AI Agent Backend",
        "version": "1.0.0",
        "environment": "production" if os.getenv("RAILWAY_ENVIRONMENT") else "development",
        "openai_configured": os.getenv("OPENAI_API_KEY") is not None,
        "supabase_configured": os.getenv("SUPABASE_URL") is not None and os.getenv("SUPABASE_KEY") is not None
    }
    return config

# Get profile data - kept for backward compatibility
@app.get("/profile")
async def profile(user_id: Optional[str] = None):
    """Get profile data"""
    try:
        logging.info(f"Getting profile data")
        profile_data = get_profile_data()
        return profile_data
    except Exception as e:
        logging.error(f"Error getting profile data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Update profile data (POST endpoint) - kept for backward compatibility
@app.post("/profile")
async def update_profile_post(profile_data: ProfileData, user_id: Optional[str] = None):
    """Update profile data using POST"""
    return await update_profile_handler(profile_data, user_id)

# Update profile data (PUT endpoint for compatibility) - kept for backward compatibility
@app.put("/profile")
async def update_profile_put(profile_data: ProfileData, user_id: Optional[str] = None):
    """Update profile data using PUT (for compatibility)"""
    return await update_profile_handler(profile_data, user_id)

# Shared handler for profile updates
async def update_profile_handler(profile_data: ProfileData, user_id: Optional[str] = None):
    """Shared handler for profile updates"""
    try:
        logging.info(f"Updating profile data")
        
        # Convert Pydantic model to dict
        profile_dict = profile_data.dict()
        
        # Update profile data in the database
        updated_profile = update_profile_data(profile_dict)
        
        # Add profile data to vector database
        add_profile_to_vector_db(updated_profile)
        
        return {"message": "Profile updated successfully", "profile": updated_profile}
    except Exception as e:
        logging.error(f"Error updating profile data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Chat endpoint - kept for backward compatibility
@app.post("/chat")
async def chat(chat_request: models.ChatRequest):
    """Process chat messages and generate AI response"""
    try:
        logging.info(f"Processing chat message")
        
        # Extract visitor information
        visitor_id = chat_request.visitor_id
        visitor_name = chat_request.visitor_name
        target_user_id = chat_request.target_user_id
        
        logging.info(f"Chat request from visitor: {visitor_id}, name: {visitor_name}, user_id: {target_user_id}")
        
        # Get the message directly from the request
        message = chat_request.message
        
        if not message or message.strip() == "":
            logging.warning("No valid user message found in request")
            return {"response": "I didn't receive a valid message. Please try again."}
        
        logging.info(f"User message: {message[:50]}...")
        
        # Get profile data
        profile_data = get_profile_data()
        logging.info(f"Retrieved profile data: {profile_data.get('id', 'No ID')}") 
        
        # Query vector database for relevant information including conversation history
        logging.info(f"Querying vector DB for relevant context and conversation history")
        search_results = query_vector_db(
            query=message, 
            n_results=3,
            visitor_id=visitor_id,
            include_conversation=True
        )
        
        # Get sequential conversation history for UI/display context
        logging.info(f"Getting sequential conversation history for visitor: {visitor_id}")
        history_limit = 10  # Get last 10 messages (5 exchanges)
        chat_history = get_chat_history(
            limit=history_limit,
            visitor_id=visitor_id,
            target_user_id=target_user_id
        )
        
        # Sort history to have oldest messages first
        if chat_history:
            chat_history = sorted(
                chat_history,
                key=lambda x: x.get("timestamp", ""),
                reverse=False  # Oldest messages first
            )
            logging.info(f"Found {len(chat_history)} previous messages in conversation history")
        else:
            logging.info("No previous conversation history found")
            chat_history = []
        
        # Generate AI response using the embeddings.py implementation
        ai_response = generate_ai_response(
            message,  # Using the message as the query
            search_results,
            profile_data,
            chat_history
        )
        
        logging.info(f"Generated AI response: {ai_response[:50]}...")
        
        # Log chat interaction
        logging.info("Saving chat message to database...")
        chat_log_result = log_chat_message(
            message=message,
            sender="user", 
            response=ai_response,
            visitor_id=chat_request.visitor_id,
            visitor_name=chat_request.visitor_name,
            target_user_id=chat_request.target_user_id
        )
        
        # Also store the conversation in the vector database for semantic search
        message_id = chat_log_result[0]["id"] if chat_log_result and len(chat_log_result) > 0 else None
        logging.info(f"Adding conversation to vector database for future reference")
        add_conversation_to_vector_db(
            message=message,
            response=ai_response,
            visitor_id=visitor_id,
            message_id=message_id
        )
        
        logging.info(f"Chat message saved: {chat_log_result is not None}")
        
        return {"response": ai_response}
    except Exception as e:
        logging.error(f"Error processing chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Get chat history endpoint - kept for backward compatibility
@app.get("/chat/history")
async def history(visitor_id: Optional[str] = None, target_user_id: Optional[str] = None, limit: int = 50):
    """Get chat history"""
    try:
        logging.info(f"Getting chat history for visitor: {visitor_id}, target: {target_user_id}, limit: {limit}")
        
        # Get chat history
        history = get_chat_history(
            limit=limit,
            visitor_id=visitor_id,
            target_user_id=target_user_id
        )
        
        logging.info(f"Retrieved {len(history)} chat history entries")
        if len(history) > 0:
            logging.info(f"First message: {history[0].get('message', 'N/A')[:30]}...")
        else:
            logging.info("No chat history found")
        
        # Convert to ChatHistoryResponse format for better compatibility
        formatted_history = []
        for item in history:
            formatted_history.append(models.ChatHistoryItem(
                id=item["id"],
                message=item["message"],
                sender=item["sender"],
                response=item.get("response"),
                visitor_id=item["visitor_id"],
                visitor_name=item.get("visitor_name"),
                target_user_id=item.get("target_user_id"),
                timestamp=item["timestamp"]
            ))
        
        response = models.ChatHistoryResponse(
            history=formatted_history,
            count=len(formatted_history)
        )
        
        logging.info(f"Returning response with {len(formatted_history)} items, using ChatHistoryResponse format")
        return response
        
    except Exception as e:
        logging.error(f"Error getting chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Run the application with uvicorn
if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser(description="AIChat API Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    uvicorn.run(
        "app.main:app", 
        host=args.host, 
        port=args.port, 
        reload=args.debug
    ) 