from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import os
import json
import uuid
from app import models
from app.database import get_profile_data, update_profile_data, log_chat_message, get_chat_history, DEFAULT_PROFILE
from app.embeddings import add_profile_to_vector_db, query_vector_db, generate_ai_response, add_conversation_to_vector_db
from app.routes import chatbot, profiles, admin, chatbots

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("backend.log"),
        logging.StreamHandler()
    ]
)

# Create the FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers from the routes directory
app.include_router(chatbot.router, prefix="/chat", tags=["chatbot"])
app.include_router(profiles.router, prefix="/profile", tags=["profiles"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(chatbots.router, prefix="/chatbots", tags=["chatbots"])

# Define models
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
    return {"message": "Welcome to the AIChat API"}

# Get profile data - kept for backward compatibility
@app.get("/profile")
async def profile(user_id: Optional[str] = None):
    """Get profile data"""
    try:
        logging.info(f"Getting profile data")
        profile_data = get_profile_data(user_id=user_id)
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
        logging.info(f"Updating profile data for user_id: {user_id}")
        
        if not user_id:
            logging.warning("No user_id provided for profile update")
            return {
                "message": "Authentication required to update profile. Please provide user_id.",
                "success": False,
                "profile": get_profile_data(None)  # Return default profile
            }
        
        # Convert Pydantic model to dict
        profile_dict = profile_data.dict(exclude_unset=True)
        
        # Update profile data in the database
        updated_profile = update_profile_data(profile_dict, user_id=user_id)
        
        if updated_profile:
            # Add profile data to vector database
            try:
                add_profile_to_vector_db(updated_profile, user_id=user_id)
                logging.info(f"Added profile to vector database for user: {user_id}")
            except Exception as vector_error:
                logging.error(f"Error adding profile to vector database: {vector_error}")
            
            return {
                "message": "Profile updated successfully", 
                "success": True,
                "profile": updated_profile
            }
        else:
            logging.error(f"Failed to update profile for user: {user_id}")
            return {
                "message": "Failed to update profile", 
                "success": False,
                "profile": get_profile_data(user_id)  # Return current profile
            }
            
    except Exception as e:
        logging.error(f"Error updating profile data: {e}", exc_info=True)
        return {
            "message": f"Error updating profile: {str(e)}", 
            "success": False,
            "profile": get_profile_data(user_id)  # Return current profile
        }

# Chat endpoint - kept for backward compatibility
@app.post("/chat")
async def chat(chat_request: models.ChatRequest):
    """Process chat messages and generate AI response"""
    try:
        logging.info(f"Processing chat message: {chat_request}")
        
        # Extract visitor information
        visitor_id = chat_request.visitor_id or "anonymous"
        visitor_name = chat_request.visitor_name
        target_user_id = chat_request.target_user_id
        
        logging.info(f"Chat request from visitor: {visitor_id}, name: {visitor_name}, user_id: {target_user_id}")
        
        # Get the message directly from the request using the helper method
        message = chat_request.get_message()
        
        if not message or message.strip() == "":
            logging.warning("No valid user message found in request")
            return {"response": "I didn't receive a valid message. Please try again."}
        
        logging.info(f"User message: {message[:50]}...")
        
        # Get profile data
        try:
            profile_data = get_profile_data(user_id=target_user_id)
            logging.info(f"Retrieved profile data: {profile_data.get('id', 'No ID')}")
        except Exception as profile_error:
            logging.error(f"Error retrieving profile data: {profile_error}")
            # Use a default profile as fallback
            profile_data = DEFAULT_PROFILE.copy()
            if target_user_id:
                profile_data['user_id'] = target_user_id
        
        # Query vector database for relevant information including conversation history
        try:
            logging.info(f"Querying vector DB for relevant context and conversation history")
            search_results = query_vector_db(
                query=message, 
                n_results=3,
                visitor_id=visitor_id,
                include_conversation=True
            )
        except Exception as vector_error:
            logging.error(f"Error querying vector database: {vector_error}")
            search_results = []
        
        # Get sequential conversation history for UI/display context
        try:
            logging.info(f"Getting sequential conversation history for visitor: {visitor_id}")
            history_limit = 10  # Get last 10 messages (5 exchanges)
            chat_history_result = get_chat_history(
                limit=history_limit,
                visitor_id=visitor_id,
                target_user_id=target_user_id
            )
            
            # Extract the history list from the result if it's a dictionary
            if isinstance(chat_history_result, dict) and 'history' in chat_history_result:
                chat_history = chat_history_result['history']
            else:
                chat_history = chat_history_result if isinstance(chat_history_result, list) else []
            
            # Sort history to have oldest messages first
            if chat_history:
                chat_history = sorted(
                    chat_history,
                    key=lambda x: x.get("timestamp", "") if isinstance(x, dict) else "",
                    reverse=False  # Oldest messages first
                )
                logging.info(f"Found {len(chat_history)} previous messages in conversation history")
            else:
                logging.info("No previous conversation history found")
                chat_history = []
        except Exception as history_error:
            logging.error(f"Error retrieving chat history: {history_error}")
            chat_history = []
        
        # Generate AI response using the embeddings.py implementation
        try:
            ai_response = generate_ai_response(
                message,  # Using the message as the query
                search_results,
                profile_data,
                chat_history
            )
            logging.info(f"Generated AI response: {ai_response[:50]}...")
        except Exception as ai_error:
            logging.error(f"Error generating AI response: {ai_error}")
            ai_response = "I'm sorry, I encountered an issue processing your request. Please try again later."
        
        # Log chat interaction
        try:
            logging.info("Saving chat message to database...")
            chat_log_success = log_chat_message(
                message=message,
                sender="user", 
                response=ai_response,
                visitor_id=visitor_id,
                visitor_name=visitor_name,
                target_user_id=target_user_id
            )
        except Exception as log_error:
            logging.error(f"Error logging chat message: {log_error}")
            chat_log_success = False
        
        # Generate a message ID for vector DB if not available from database
        message_id = str(uuid.uuid4())
        
        # Also store the conversation in the vector database for semantic search
        try:
            logging.info(f"Adding conversation to vector database with message_id: {message_id}")
            add_conversation_to_vector_db(
                message=message,
                response=ai_response,
                visitor_id=visitor_id,
                message_id=message_id
            )
        except Exception as vector_store_error:
            logging.error(f"Error storing conversation in vector DB: {vector_store_error}")
        
        logging.info(f"Chat message saved: {chat_log_success}")
        
        return {"response": ai_response}
    except Exception as e:
        logging.error(f"Error processing chat: {str(e)}", exc_info=True)
        # Return a user-friendly error message
        return {"response": "I'm sorry, I encountered an error processing your message. Please try again later.", "error": str(e)}

# Get chat history endpoint - kept for backward compatibility
@app.get("/chat/history")
async def history(visitor_id: Optional[str] = None, target_user_id: Optional[str] = None, limit: int = 50):
    """Get chat history"""
    try:
        logging.info(f"Getting chat history for visitor: {visitor_id}, target: {target_user_id}, limit: {limit}")
        
        # Get chat history with error handling
        try:
            history_result = get_chat_history(
                limit=limit,
                visitor_id=visitor_id,
                target_user_id=target_user_id
            )
        except Exception as get_history_error:
            logging.error(f"Error retrieving chat history from database: {get_history_error}")
            # Return empty history instead of failing
            return models.ChatHistoryResponse(
                history=[],
                count=0
            )
        
        # Convert each history item to a ChatHistoryItem model
        formatted_history = []
        
        # Ensure history_result is a list
        if not isinstance(history_result, list):
            logging.warning(f"Unexpected history result type: {type(history_result)}")
            # Try to extract history list if it's a dict
            if isinstance(history_result, dict) and 'history' in history_result:
                history_result = history_result['history']
            else:
                # If we can't extract a valid list, return empty
                return models.ChatHistoryResponse(
                    history=[],
                    count=0
                )
        
        # Process each history item
        for item in history_result:
            if not isinstance(item, dict):
                logging.warning(f"Skipping invalid history item type: {type(item)}")
                continue
                
            try:
                # Create ChatHistoryItem with safe defaults
                history_item = models.ChatHistoryItem(
                    id=item.get("id", str(uuid.uuid4())),
                    message=item.get("message", ""),
                    sender=item.get("sender", "unknown"),
                    response=item.get("response", ""),
                    visitor_id=item.get("visitor_id", visitor_id or "unknown"),
                    visitor_name=item.get("visitor_name", ""),
                    target_user_id=item.get("user_id", target_user_id),
                    timestamp=item.get("timestamp", "") or item.get("created_at", "")
                )
                formatted_history.append(history_item)
            except Exception as format_error:
                logging.error(f"Error formatting history item: {format_error}, item: {item}")
                # Skip this item and continue to the next
                continue
        
        # Create the response
        response = models.ChatHistoryResponse(
            history=formatted_history,
            count=len(formatted_history)
        )
        
        logging.info(f"Returning chat history with {len(formatted_history)} items")
        return response
    except Exception as e:
        logging.error(f"Unhandled error in chat history endpoint: {str(e)}", exc_info=True)
        # Always return a valid response, even on error
        return models.ChatHistoryResponse(
            history=[],
            count=0
        )

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