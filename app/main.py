from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import os
import json
import uuid
import time
from app import models
from app.database import get_profile_data, update_profile_data, log_chat_message, get_chat_history, DEFAULT_PROFILE, supabase, update_profile_in_memory_only, add_project
from app.embeddings import add_profile_to_vector_db, query_vector_db, generate_ai_response, add_conversation_to_vector_db
from app.routes import chatbot, profiles, admin, chatbots

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
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
    target_user_id: Optional[str] = None
    chatbot_id: Optional[str] = None

# Define models for projects
class ProjectData(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    details: Optional[str] = None
    content: Optional[str] = None
    id: Optional[str] = None

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to the AIChat API"}

# Get profile data - kept for backward compatibility
@app.get("/profile")
async def profile(user_id: Optional[str] = None, request: Request = None):
    """Get profile data"""
    try:
        logging.info(f"Getting profile data")
        
        # Try to extract user_id from request headers if not provided
        if not user_id and request and request.headers.get("Authorization"):
            try:
                # Extract user_id from auth header
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header.replace("Bearer ", "")
                    # Verify token and extract user_id
                    user_id = verify_token(token)
                    logging.info(f"Extracted user_id from auth token: {user_id}")
            except Exception as auth_error:
                logging.error(f"Error extracting user_id from auth: {auth_error}")
        
        profile_data = get_profile_data(user_id=user_id)
        return profile_data
    except Exception as e:
        logging.error(f"Error getting profile data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Update profile data (POST endpoint) - kept for backward compatibility
@app.post("/profile")
async def update_profile_post(profile_data: ProfileData, user_id: Optional[str] = None, request: Request = None):
    """Update profile data using POST"""
    return await update_profile_handler(profile_data, user_id, request)

# Update profile data (PUT endpoint for compatibility) - kept for backward compatibility
@app.put("/profile")
async def update_profile_put(profile_data: ProfileData, user_id: Optional[str] = None, request: Request = None):
    """Update profile data using PUT (for compatibility)"""
    return await update_profile_handler(profile_data, user_id, request)

# Shared handler for profile updates
async def update_profile_handler(profile_data: ProfileData, user_id: Optional[str] = None, request: Request = None):
    """Shared handler for profile updates"""
    try:
        logging.info("===== STARTING PROFILE UPDATE =====")
        
        # Get the authenticated user from the request if available
        authenticated_user = None
        if request:
            try:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header.replace("Bearer ", "")
                    logging.info(f"Found auth token in request header")
                    # Verify token and extract user ID
                    authenticated_user = verify_token(token)
                    if authenticated_user:
                        logging.info(f"Authenticated as user: {authenticated_user}")
                        # Override user_id with authenticated user
                        user_id = authenticated_user
            except Exception as auth_error:
                logging.error(f"Auth error: {auth_error}")
        
        if not user_id:
            logging.warning("No user_id provided for profile update")
            # For testing purposes, use a fixed user_id if in development mode
            if os.getenv("ENVIRONMENT") != "production":
                test_user_id = os.getenv("TEST_USER_ID")
                if test_user_id:
                    logging.info(f"Using test user_id for development: {test_user_id}")
                    user_id = test_user_id
                else:
                    logging.warning("No TEST_USER_ID environment variable set for development")
            
            if not user_id:
                return {
                    "message": "Authentication required to update profile. Please provide user_id.",
                    "success": False,
                    "profile": get_profile_data(None)  # Return default profile
                }
        
        # Convert Pydantic model to dict
        profile_dict = profile_data.dict(exclude_unset=True)
        
        # List of expected profile fields for debugging
        expected_fields = ["bio", "skills", "experience", "interests", "name", "location", "projects"]
        
        # Log which fields are present and which are missing
        present_fields = [field for field in expected_fields if field in profile_dict]
        missing_fields = [field for field in expected_fields if field not in profile_dict]
        
        logging.info(f"Present fields: {present_fields}")
        logging.info(f"Missing fields: {missing_fields}")
        
        # Explicitly check for each field and log its value
        for field in expected_fields:
            if field in profile_dict:
                logging.info(f"Field '{field}' value: {profile_dict[field]}")
            else:
                logging.info(f"Field '{field}' is not included in the update")
        
        # Ensure all empty string fields are converted to None to prevent overwriting with empty strings
        for key, value in profile_dict.items():
            if isinstance(value, str) and value.strip() == '':
                profile_dict[key] = None
                logging.info(f"Converting empty string to None for field: {key}")
        
        # IMPORTANT: Get current profile to ensure fields that aren't being updated remain intact
        current_profile = get_profile_data(user_id)
        logging.info(f"Current profile before update: {current_profile}")
        
        # Merge the current profile with the update, only changing fields that are explicitly provided
        # This helps ensure fields not included in the update aren't lost
        merged_profile = current_profile.copy()
        for field in expected_fields:
            if field in profile_dict:
                merged_profile[field] = profile_dict[field]
                logging.info(f"Updating field '{field}' with value: {profile_dict[field]}")
            else:
                logging.info(f"Keeping existing value for field '{field}': {merged_profile.get(field)}")
                
        # Special handling for nested fields
        if 'project_list' in profile_dict:
            merged_profile['project_list'] = profile_dict['project_list']
            
        # Use the merged profile for the update
        profile_dict = merged_profile
        logging.info(f"Final merged profile data for update: {profile_dict}")
        
        # For dev/testing, always use in-memory update to avoid database constraints
        if os.getenv("ENVIRONMENT") != "production":
            logging.info("Using in-memory update directly in development mode")
            # Update profile in memory only
            updated_profile = update_profile_in_memory_only(profile_dict, user_id=user_id)
            logging.info("Used in-memory update since we're in development mode")
            
            # Log the updated profile that was returned
            logging.info(f"Updated profile after in-memory update: {updated_profile.get('profile', {})}")
            
        # If not in development mode, try database update
        else:
            logging.info("Attempting database update for profile")
            updated_profile = update_profile_data(profile_dict, user_id=user_id)
            
            # If database update fails, try in-memory fallback
            if not updated_profile or not updated_profile.get("success", False):
                logging.warning("Database update failed, using in-memory fallback")
                updated_profile = update_profile_in_memory_only(profile_dict, user_id=user_id)
        
        # Check if the update was successful (either via DB or in-memory)
        if updated_profile and updated_profile.get("success", False):
            # Add profile data to vector database
            try:
                add_profile_to_vector_db(updated_profile.get("profile", {}), user_id=user_id)
                logging.info(f"Added profile to vector database for user: {user_id}")
            except Exception as vector_error:
                logging.error(f"Error adding profile to vector database: {vector_error}")
            
            # Log all fields in the updated profile to verify they were properly updated
            profile_to_return = updated_profile.get("profile", {})
            logging.info(f"Profile fields after update:")
            for field in expected_fields:
                if field in profile_to_return:
                    logging.info(f"Updated field '{field}': {profile_to_return[field]}")
                else:
                    logging.info(f"Field '{field}' not present in updated profile")
            
            logging.info("===== PROFILE UPDATE COMPLETED SUCCESSFULLY =====")
            return {
                "message": "Profile updated successfully", 
                "success": True,
                "profile": profile_to_return
            }
        else:
            error_message = updated_profile.get("message", "Failed to update profile") if updated_profile else "Failed to update profile"
            logging.error(f"Failed to update profile for user: {user_id}. Error: {error_message}")
            logging.info("===== PROFILE UPDATE FAILED =====")
            return {
                "message": error_message, 
                "success": False,
                "profile": get_profile_data(user_id)  # Return current profile
            }
            
    except Exception as e:
        logging.error(f"Error updating profile data: {e}", exc_info=True)
        logging.info("===== PROFILE UPDATE FAILED WITH EXCEPTION =====")
        return {
            "message": f"Error updating profile: {str(e)}", 
            "success": False,
            "profile": get_profile_data(user_id)  # Return current profile
        }

# Helper function to verify token and extract user_id
def verify_token(token):
    """
    Verify JWT token and extract user_id
    This is a simplified implementation - in production, you should use a proper JWT library
    """
    try:
        # Use Supabase client to get user from token
        user_response = supabase.auth.get_user(token)
        if user_response and hasattr(user_response, 'user') and user_response.user:
            return user_response.user.id
            
        return None
    except Exception as e:
        logging.error(f"Error verifying token: {e}")
        return None

# Chat endpoint - kept for backward compatibility
@app.post("/chat")
async def chat(chat_request: models.ChatRequest):
    """Process chat messages and generate AI response"""
    try:
        logging.info("===== PROCESSING CHAT REQUEST =====")
        
        # Extract parameters from request
        message = chat_request.message
        visitor_id = chat_request.visitor_id
        visitor_name = chat_request.visitor_name
        target_user_id = chat_request.target_user_id
        chatbot_id = chat_request.chatbot_id
        
        # Log request parameters
        logging.info(f"Chat request: message='{message[:30]}...', visitor_id={visitor_id}, target_user_id={target_user_id}")
        
        # Normalize visitor ID
        if not visitor_id:
            visitor_id = f"anonymous-{int(time.time())}"
            logging.info(f"Generated visitor ID: {visitor_id}")
            
        # Normalize visitor name
        if not visitor_name:
            visitor_name = "Anonymous"
        
        # Start by retrieving existing chat history
        try:
            chat_history = get_chat_history(
                limit=20,  # Last 20 messages
                visitor_id=visitor_id,
                target_user_id=target_user_id
            )
            logging.info(f"Retrieved {len(chat_history)} chat history items")
        except Exception as history_error:
            logging.error(f"Error retrieving chat history: {history_error}")
            chat_history = []
        
        # Get profile data for this target user if provided
        profile_data = {}
        if target_user_id:
            try:
                profile_data = get_profile_data(target_user_id)
                logging.info(f"Retrieved profile data for target user: {target_user_id}")
                
                # Make sure project_list is always present
                if 'project_list' not in profile_data:
                    profile_data['project_list'] = []
                    
                # Log profile fields available
                fields = list(profile_data.keys())
                logging.info(f"Profile fields available: {fields}")
                
                # Check for project_list
                project_count = len(profile_data.get('project_list', []))
                logging.info(f"Profile has {project_count} projects")
                
            except Exception as profile_error:
                logging.error(f"Error retrieving profile data: {profile_error}")
                profile_data = {}
                
        # Vector search for relevant content based on the user's message
        try:
            search_results = query_vector_db(
                query=message, 
                n_results=3,
                user_id=target_user_id,  # Use target_user_id for user-specific collections
                visitor_id=visitor_id,
                include_conversation=True
            )
            logging.info(f"Vector search returned {len(search_results)} results")
        except Exception as search_error:
            logging.error(f"Error during vector search: {search_error}")
            search_results = []
        
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
        
        # Log chat interaction - Critical to pass the correct target_user_id
        try:
            logging.info(f"Saving chat message to database for target user: {target_user_id}")
            chat_log_success = log_chat_message(
                message=message,
                sender="user", 
                response=ai_response,
                visitor_id=visitor_id,
                visitor_name=visitor_name,
                target_user_id=target_user_id,  # This is the auth.users.id
                chatbot_id=chatbot_id
            )
            logging.info(f"Chat message saved successfully: {chat_log_success}")
        except Exception as log_error:
            logging.error(f"Error logging chat message: {log_error}")
            chat_log_success = False
        
        # Generate a message ID for vector DB
        message_id = str(uuid.uuid4())
        
        # Also store the conversation in the vector database for semantic search
        try:
            logging.info(f"Adding conversation to vector database with message_id: {message_id}")
            add_conversation_to_vector_db(
                message=message,
                response=ai_response,
                visitor_id=visitor_id,
                message_id=message_id,
                user_id=target_user_id  # Pass target_user_id for user-specific collections
            )
        except Exception as vector_store_error:
            logging.error(f"Error storing conversation in vector DB: {vector_store_error}")
        
        # Fetch updated chat history to return
        try:
            updated_history = get_chat_history(
                limit=20,  # Last 20 messages
                visitor_id=visitor_id,
                target_user_id=target_user_id
            )
            logging.info(f"Retrieved {len(updated_history)} updated chat history items")
        except Exception as updated_history_error:
            logging.error(f"Error retrieving updated chat history: {updated_history_error}")
            updated_history = []
        
        logging.info("===== COMPLETED CHAT REQUEST =====")
        
        # Return the response to the user along with updated chat history
        return {
            "response": ai_response,
            "chat_history": updated_history,
            "success": True
        }
    except Exception as e:
        logging.error(f"Error in chat endpoint: {e}", exc_info=True)
        return {
            "response": "I apologize, but I encountered an error processing your message. Please try again.",
            "chat_history": [],
            "success": False
        }

# Get chat history endpoint - kept for backward compatibility
@app.get("/chat/history")
async def history(visitor_id: Optional[str] = None, target_user_id: Optional[str] = None, limit: int = 50):
    """Get chat history"""
    try:
        logging.info(f"Getting chat history for visitor: {visitor_id}, target user: {target_user_id}, limit: {limit}")
        
        # Verify at least one filter is provided
        if not visitor_id and not target_user_id:
            logging.warning("No visitor_id or target_user_id provided - cannot fetch history")
            return models.ChatHistoryResponse(
                history=[],
                count=0,
                success=False,
                message="Please provide either visitor_id or target_user_id"
            )
        
        # Get chat history with appropriate error handling
        try:
            history_result = get_chat_history(
                limit=limit,
                visitor_id=visitor_id,
                target_user_id=target_user_id
            )
            
            # Log detailed info about the history result
            logging.info(f"History result type: {type(history_result)}")
            logging.info(f"History result length: {len(history_result) if isinstance(history_result, list) else 'not a list'}")
            
            # Ensure history_result is a list
            if not isinstance(history_result, list):
                logging.error(f"Unexpected history result type: {type(history_result)}")
                history_result = []
                
            logging.info(f"Successfully retrieved {len(history_result)} history items")
        except Exception as get_history_error:
            logging.error(f"Error retrieving chat history from database: {get_history_error}", exc_info=True)
            # Return empty history instead of failing
            return models.ChatHistoryResponse(
                history=[],
                count=0,
                success=False,
                message=f"Error retrieving chat history: {str(get_history_error)}"
            )
        
        # Convert history items to ChatHistoryItem model format
        formatted_history = []
        
        # Process each history item
        for i, item in enumerate(history_result):
            if not isinstance(item, dict):
                logging.warning(f"Skipping invalid history item type at index {i}: {type(item)}")
                continue
                
            try:
                # Log item details for debugging (just the first few items)
                if i < 2:
                    logging.info(f"Item {i} keys: {list(item.keys())}")
                    logging.info(f"Item {i} values sample: id={item.get('id', 'unknown')}, message={item.get('message', 'unknown')[:20]}")
                
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
                logging.error(f"Error formatting history item at index {i}: {format_error}", exc_info=True)
                # Skip this item and continue to the next
                continue
        
        # Sort by timestamp if available (newest first for display)
        try:
            formatted_history.sort(
                key=lambda x: x.timestamp if x.timestamp else "",
                reverse=True  # newest first
            )
        except Exception as sort_error:
            logging.error(f"Error sorting history: {sort_error}", exc_info=True)
        
        # Create the response
        response = models.ChatHistoryResponse(
            history=formatted_history,
            count=len(formatted_history),
            success=True,
            message=f"Retrieved {len(formatted_history)} messages"
        )
        
        logging.info(f"Returning chat history with {len(formatted_history)} items")
        return response
    except Exception as e:
        logging.error(f"Unhandled error in chat history endpoint: {str(e)}", exc_info=True)
        # Always return a valid response, even on error
        return models.ChatHistoryResponse(
            history=[],
            count=0,
            success=False,
            message=f"Error: {str(e)}"
        )

# Projects endpoints
@app.post("/projects")
async def create_project(project_data: ProjectData, user_id: Optional[str] = None, request: Request = None):
    """Create a new project"""
    try:
        # Try to extract user_id from request headers if not provided
        if not user_id and request and request.headers.get("Authorization"):
            try:
                # Extract user_id from auth header
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header.replace("Bearer ", "")
                    # Verify token and extract user_id
                    user_id = verify_token(token)
                    logging.info(f"Extracted user_id from auth token: {user_id}")
            except Exception as auth_error:
                logging.error(f"Error extracting user_id from auth: {auth_error}")
                
        logging.info(f"Creating project for user_id: {user_id}")
        
        if not user_id:
            logging.warning("No user_id provided for project creation")
            # For testing purposes, use a fixed user_id if in development mode
            if os.getenv("ENVIRONMENT") != "production":
                test_user_id = os.getenv("TEST_USER_ID")
                if test_user_id:
                    logging.info(f"Using test user_id for development: {test_user_id}")
                    user_id = test_user_id
                else:
                    logging.warning("No TEST_USER_ID environment variable set for development")
            
            if not user_id:
                return {
                    "message": "Authentication required to create project. Please provide user_id.",
                    "success": False,
                    "project": None
                }
        
        # Convert Pydantic model to dict
        project_dict = project_data.dict(exclude_unset=True)
        
        # Log the project data being created
        logging.info(f"Creating project: {project_dict}")
        
        # Use the add_project function to add the project
        result = add_project(project_dict, user_id=user_id)
        
        if result and result.get("success", False):
            return {
                "message": "Project created successfully",
                "success": True,
                "project": result.get("project", {}).get("project_list", [])[-1] if result.get("project", {}).get("project_list") else None,
                "profile": result.get("profile", {})
            }
        else:
            error_message = result.get("message", "Failed to create project") if result else "Failed to create project"
            logging.error(f"Failed to create project. Error: {error_message}")
            return {
                "message": error_message,
                "success": False,
                "project": None
            }
    except Exception as e:
        logging.error(f"Error creating project: {e}", exc_info=True)
        return {
            "message": f"Error creating project: {str(e)}",
            "success": False,
            "project": None
        }

@app.get("/projects")
async def get_projects(user_id: Optional[str] = None, request: Request = None):
    """Get projects for a specific user"""
    try:
        logging.info("===== GETTING USER PROJECTS =====")
        
        # Try to extract user_id from request headers if not provided
        authenticated_user = None
        if not user_id and request and request.headers.get("Authorization"):
            try:
                # Extract user_id from auth header
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header.replace("Bearer ", "")
                    # Verify token and extract user_id
                    authenticated_user = verify_token(token)
                    user_id = authenticated_user
                    logging.info(f"Using authenticated user for projects: {user_id}")
            except Exception as auth_error:
                logging.error(f"Error extracting user_id from auth: {auth_error}")
        
        if not user_id:
            logging.warning("No user_id provided for projects request")
            # For testing purposes, use a fixed user_id if in development mode
            if os.getenv("ENVIRONMENT") != "production":
                test_user_id = os.getenv("TEST_USER_ID")
                if test_user_id:
                    logging.info(f"Using test user_id for development: {test_user_id}")
                    user_id = test_user_id
                else:
                    logging.warning("No TEST_USER_ID environment variable set for development")
            
            if not user_id:
                return {
                    "message": "User ID is required to fetch projects",
                    "success": False,
                    "projects": []
                }
                
        logging.info(f"Fetching projects for user: {user_id}")
        
        # Fetch projects directly from the database
        if supabase:
            try:
                response = supabase.table("projects").select("*").eq("user_id", user_id).execute()
                
                if response and hasattr(response, 'data'):
                    projects = response.data
                    logging.info(f"Found {len(projects)} projects in database")
                    
                    return {
                        "message": "Projects retrieved successfully",
                        "success": True,
                        "projects": projects
                    }
                else:
                    logging.warning("No projects found in database or invalid response")
                    return {
                        "message": "No projects found",
                        "success": True,
                        "projects": []
                    }
            except Exception as db_error:
                logging.error(f"Database error fetching projects: {db_error}")
                # Fall back to profile data
        
        # Fallback method: get projects from profile data
        profile_data = get_profile_data(user_id)
        
        if profile_data and 'project_list' in profile_data:
            projects = profile_data['project_list']
            logging.info(f"Found {len(projects)} projects in profile data")
            return {
                "message": "Projects retrieved from profile data",
                "success": True,
                "projects": projects
            }
        else:
            logging.warning("No projects found in profile data")
            return {
                "message": "No projects found",
                "success": True,
                "projects": []
            }
    
    except Exception as e:
        logging.error(f"Error fetching projects: {e}", exc_info=True)
        return {
            "message": f"Error fetching projects: {str(e)}",
            "success": False,
            "projects": []
        }

@app.get("/chat/history")
async def get_chat_history_endpoint(
    visitor_id: Optional[str] = None,
    target_user_id: Optional[str] = None,
    chatbot_id: Optional[str] = None,
    limit: int = 50
):
    """Get chat history for a visitor and target user"""
    try:
        logging.info(f"Retrieving chat history: visitor_id={visitor_id}, target_user_id={target_user_id}, limit={limit}")
        
        if not visitor_id and not target_user_id and not chatbot_id:
            return {
                "success": False,
                "message": "At least one filter (visitor_id, target_user_id, or chatbot_id) is required",
                "history": []
            }
        
        history = get_chat_history(
            limit=limit,
            visitor_id=visitor_id,
            target_user_id=target_user_id,
            chatbot_id=chatbot_id
        )
        
        logging.info(f"Retrieved {len(history)} chat history items")
        
        return {
            "success": True,
            "message": "Chat history retrieved successfully",
            "history": history
        }
    except Exception as e:
        logging.error(f"Error retrieving chat history: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error retrieving chat history: {str(e)}",
            "history": []
        }

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