from fastapi import FastAPI, Request, Depends, HTTPException, File, UploadFile, Form, Body, BackgroundTasks, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
import logging
import os
import json
import uuid
from app import models
from app.database import get_profile_data, update_profile_data, log_chat_message, get_chat_history, get_or_create_chatbot, get_or_create_conversation, get_or_create_visitor
from app.embeddings import add_profile_to_vector_db, query_vector_db, generate_ai_response, add_conversation_to_vector_db
from app.routes import chatbot, profiles, admin
import time
import openai
from dotenv import load_dotenv
from app.auth import get_current_user, User
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, FileResponse, JSONResponse
import re
import jwt
from fastapi.staticfiles import StaticFiles
from app.routes import chatbot as chatbot_routes
from app.routes import documents

# EMERGENCY FIX - Import the emergency endpoint
try:
    from app.bypass_auth import emergency_chat_endpoint, ChatResponse
    EMERGENCY_MODE = True
    logging.info("🚨 EMERGENCY MODE ENABLED: Using authentication bypass")
except ImportError:
    EMERGENCY_MODE = False
    logging.warning("❌ Emergency mode not available")

try:
    from app.routes import auth
except ImportError:
    logging.warning("Auth routes not imported. Make sure app/routes/auth.py exists.")

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("backend.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configure OpenAI
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("Missing OpenAI API key. Set OPENAI_API_KEY in .env file.")

try:
    # Initialize OpenAI client
    openai.api_key = openai_api_key
    # Test the API key with a simple request - but don't crash if it fails
    try:
        openai.models.list()
        logger.info("Successfully initialized OpenAI client")
    except Exception as api_error:
        logger.warning(f"OpenAI API list models test failed: {str(api_error)}")
        logger.warning("Continuing with application startup despite API test failure")
except Exception as e:
    logger.error(f"Error initializing OpenAI client: {str(e)}")
    if "invalid_api_key" in str(e).lower():
        logger.error("Invalid API key format detected. Please check your OpenAI API key format.")
    # Log the error but don't crash the application
    logger.warning("Continuing application startup despite OpenAI client initialization issue")

# Create the FastAPI app
app = FastAPI()

# Authentication middleware
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Public paths that don't require authentication
        public_paths = [
            r"^/$",                      # Root path
            r"^/docs",                   # Swagger documentation
            r"^/redoc",                  # ReDoc
            r"^/openapi.json",           # OpenAPI schema
            r"^/profile",                # TEMP: Make profile endpoint public for testing
            r"^/chat/public",            # Public chat endpoints
            r"^/chat/[^/]+/public$",     # Public chatbot endpoint for specific user (GET and POST)
            r"^/chat/[^/]+/public/history", # Public chat history endpoint
            r"^/profile/public",         # Public profile endpoints
            r"^/emergency-chat",         # Emergency chat endpoint
            r"^/check-chat",             # Chat status check
            r"^/chat$",                  # Main chat endpoint
            r"^/chat/history",           # Chat history endpoint
        ]
        
        # Check if the current path is in the public paths
        path = request.url.path
        for pattern in public_paths:
            if re.match(pattern, path):
                return await call_next(request)
        
        # If path requires authentication, check for Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response(
                status_code=401,
                content=json.dumps({"detail": "Not authenticated"}),
                media_type="application/json"
            )
        
        # Continue with the request
        return await call_next(request)

# Add middleware
app.add_middleware(AuthMiddleware)

# Add CORS middleware
allowed_origins = [
    "http://localhost:3000",                                           # Local development
    "https://agentclone-9gfdyhwxp-cirils-projects-86482382.vercel.app" # Your specific Vercel deployment
]

# Add any additional origins from environment variable if set
cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
if cors_origins_env:
    additional_origins = [origin.strip() for origin in cors_origins_env.split(",")]
    allowed_origins.extend(additional_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers from the routes directory
app.include_router(chatbot.router, prefix="/chat", tags=["chatbot"])
app.include_router(profiles.router, prefix="/profile", tags=["profiles"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
try:
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
except NameError:
    logging.warning("Auth router not included. Authentication endpoints will not be available.")

# Add the chatbot routes
app.include_router(chatbot_routes.router)

# Define models
class ProfileData(BaseModel):
    bio: Optional[str] = None
    skills: Optional[str] = None
    experience: Optional[str] = None
    projects: Optional[str] = None
    interests: Optional[str] = None
    name: Optional[str] = None
    location: Optional[str] = None
    user_id: Optional[str] = None  # Add user_id field for Supabase
    calendly_link: Optional[str] = None  # Calendly meeting scheduling link
    meeting_rules: Optional[str] = None  # Rules for allowing meeting requests

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    user_id: Optional[str] = None  # Kept for API compatibility but not used
    visitor_id: Optional[str] = None
    visitor_name: Optional[str] = None
    chatbot_id: Optional[str] = None

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to the AIChat API"}

# Get profile data - kept for backward compatibility
@app.get("/profile")
async def profile(user_id: Optional[str] = None, request: Request = None):
    """Get profile data"""
    try:
        # Try to extract JWT from request
        effective_user_id = user_id
        if request and request.headers.get("Authorization"):
            auth_header = request.headers.get("Authorization")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
            
            if token:
                try:
                    # Decode JWT to get user ID
                    payload = jwt.decode(token, options={"verify_signature": False})
                    jwt_user_id = payload.get("sub")
                    if jwt_user_id:
                        logging.info(f"Extracted user_id from JWT: {jwt_user_id}")
                        effective_user_id = jwt_user_id
                except Exception as jwt_error:
                    logging.warning(f"Error decoding JWT: {jwt_error}")
        
        logging.info(f"Getting profile data for user_id: {effective_user_id}")
        profile_data = get_profile_data(user_id=effective_user_id)
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
        # Try to extract JWT from request
        effective_user_id = user_id
        if request and request.headers.get("Authorization"):
            auth_header = request.headers.get("Authorization")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
            
            if token:
                try:
                    # Decode JWT to get user ID
                    payload = jwt.decode(token, options={"verify_signature": False})
                    jwt_user_id = payload.get("sub")
                    if jwt_user_id:
                        logging.info(f"Extracted user_id from JWT: {jwt_user_id}")
                        effective_user_id = jwt_user_id
                except Exception as jwt_error:
                    logging.warning(f"Error decoding JWT: {jwt_error}")
        
        logging.info(f"Updating profile data for user_id: {effective_user_id}")
        
        # Convert Pydantic model to dict
        profile_dict = profile_data.dict(exclude_unset=True)
        
        # Log data for debugging
        logging.info(f"Profile data received: {profile_dict}")
        logging.info(f"User ID from query param: {user_id}")
        logging.info(f"User ID from profile data: {profile_dict.get('user_id')}")
        
        # Check for user_id in profile_data, fall back to extracted JWT user_id or query param if not provided
        profile_user_id = profile_dict.get('user_id')
        final_user_id = profile_user_id or effective_user_id
        
        if final_user_id:
            logging.info(f"Using final user_id: {final_user_id}")
            # Ensure the user_id is also in the profile data
            profile_dict['user_id'] = final_user_id
        
        # Update profile data in the database
        updated_profile = update_profile_data(profile_dict, final_user_id)
        
        if not updated_profile:
            logging.error("Failed to update profile data")
            raise HTTPException(status_code=500, detail="Failed to update profile data")
        
        # Add profile data to vector database
        add_profile_to_vector_db(updated_profile)
        
        return {"message": "Profile updated successfully", "profile": updated_profile}
    except Exception as e:
        logging.error(f"Error updating profile data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper function to check if meeting request is valid based on rules
def is_valid_meeting_request(message: str, meeting_rules: str) -> bool:
    """
    Check if a meeting request is valid based on the configured rules
    """
    if not meeting_rules:
        return True  # If no rules are set, allow all meeting requests
        
    # Convert message and rules to lowercase for case-insensitive matching
    message = message.lower()
    rules = meeting_rules.lower()
    
    # Common meeting request keywords
    meeting_keywords = ["meet", "meeting", "schedule", "appointment", "chat", "discuss", "call"]
    
    # Check if this is actually a meeting request
    is_meeting_request = any(keyword in message for keyword in meeting_keywords)
    if not is_meeting_request:
        return False
        
    # Extract purposes mentioned in the rules
    # Example rule: "Only allow meetings for: project discussions, job opportunities, consulting"
    allowed_purposes = [purpose.strip() for purpose in rules.split(",")]
    
    # Check if any of the allowed purposes are mentioned in the message
    return any(purpose in message for purpose in allowed_purposes)

# Update the chat function to use conversations
@app.post("/chat")
async def chat(chat_request: models.ChatRequest):
    try:
        # Get the latest user message
        user_message = chat_request.message # Assuming ChatRequest now has a direct 'message' field based on previous log
        if not user_message:
            user_message = chat_request.messages[-1].content if chat_request.messages else ""
        
        user_message_lower = user_message.lower()
        
        # Extract identifying information
        visitor_id = chat_request.visitor_id
        chatbot_id = chat_request.chatbot_id
        target_user_id = chat_request.target_user_id # Used to find default chatbot if chatbot_id is missing
        visitor_name = chat_request.visitor_name # For visitor creation/update
        
        if not chatbot_id and target_user_id:
            logger.info(f"No chatbot_id provided, looking up default for target_user_id: {target_user_id}")
            chatbot_data = get_or_create_chatbot(user_id=target_user_id)
            if chatbot_data:
                chatbot_id = chatbot_data.get("id")
                logger.info(f"Using default chatbot_id: {chatbot_id}")
            else:
                logger.error(f"Could not find or create a default chatbot for user {target_user_id}")
                raise HTTPException(status_code=404, detail="Chatbot configuration not found.")
        
        if not chatbot_id:
            logger.error("Chatbot ID is missing and could not be determined.")
            raise HTTPException(status_code=400, detail="Chatbot ID is required.")
        
        if not visitor_id:
            # Generate a visitor ID if one is not provided (or handle error)
            visitor_id = str(uuid.uuid4())
            logger.warning(f"No visitor_id provided, generated a new one: {visitor_id}")
            # Optionally, you might want to raise an error if visitor_id is strictly required
            # raise HTTPException(status_code=400, detail="Visitor ID is required.")

        # Ensure visitor exists in the visitors table (using the separate function)
        try:
            visitor_record = get_or_create_visitor(visitor_id, visitor_name)
            # Use the UUID from the visitor record for consistency, if available
            db_visitor_id = visitor_record.get("id") if visitor_record else visitor_id
            if not db_visitor_id:
                logger.error(f"Failed to get or create visitor, using original ID: {visitor_id}")
                db_visitor_id = visitor_id # Fallback, though this might cause issues if it's not a UUID
            else:
                logger.info(f"Ensured visitor exists with UUID: {db_visitor_id}")
        except Exception as visitor_err:
            logger.error(f"Error ensuring visitor exists: {visitor_err}")
            # Decide how to proceed: raise error or continue with potentially non-UUID visitor_id?
            # For now, let's try continuing, get_or_create_conversation might raise an error if format is wrong
            db_visitor_id = visitor_id 

        # Get or create the conversation ID
        conversation_id = get_or_create_conversation(chatbot_id=str(chatbot_id), visitor_id=str(db_visitor_id))
        logger.info(f"Using conversation_id: {conversation_id}")

        # --- Meeting Request Logic (remains largely the same, but uses chatbot owner ID) ---
        chatbot_data = get_or_create_chatbot(chatbot_id=chatbot_id) # Fetch chatbot data again to get owner ID safely
        owner_user_id = chatbot_data.get("user_id")
        
        if any(keyword in user_message_lower for keyword in ["meet", "meeting", "schedule", "appointment", "chat", "discuss", "call"]):
            profile_data = get_profile_data(user_id=owner_user_id)
            if profile_data and profile_data.get("calendly_link"):
                if is_valid_meeting_request(user_message, profile_data.get("meeting_rules", "")):
                    calendly_link = profile_data["calendly_link"]
                    meeting_response = (
                        f"I'd be happy to help you schedule a meeting! You can use my Calendly link to find a suitable time: "
                        f"{calendly_link}\n\nPlease select a time that works best for you."
                    )
                    # Log this interaction as well
                    log_chat_message(conversation_id=conversation_id, message=user_message, response=meeting_response, sender="user")
                    return models.ChatResponse(response=meeting_response)
                else:
                    meeting_response = ("I understand you'd like to schedule a meeting. However, based on our meeting policy, "
                                      "I can only schedule meetings for specific purposes. Could you please clarify the purpose "
                                      "of the meeting?")
                    log_chat_message(conversation_id=conversation_id, message=user_message, response=meeting_response, sender="user")
                    return models.ChatResponse(response=meeting_response)
        # --- End Meeting Request Logic ---

        logging.info(f"Processing normal chat message for conversation {conversation_id}")

        if not user_message or user_message.strip() == "":
            logging.warning("No valid user message found in request")
            return models.ChatResponse(response="I didn't receive a valid message. Please try again.")
        
        # Get profile data for the chatbot owner
        profile_data = get_profile_data(user_id=owner_user_id)
        logging.info(f"Retrieved profile data for owner {owner_user_id}: {profile_data.get('id', 'No ID')}") 
        
        # Query vector database (remains similar, but context might change)
        logging.info(f"Querying vector DB for relevant context for conversation {conversation_id}")
        search_results = query_vector_db(
            query=user_message, 
            n_results=3,
            user_id=owner_user_id, # Filter context by chatbot owner
            # visitor_id=db_visitor_id, # Optional: Could filter context by visitor too
            # include_conversation=True # This might need adjustment based on how history is stored in vector DB
        )
        
        # Get sequential conversation history using the new function
        logging.info(f"Getting sequential conversation history for conversation: {conversation_id}")
        history_limit = 10 
        chat_history = get_chat_history(
            conversation_id=conversation_id,
            limit=history_limit
        )
        
        # Sort history (already sorted by DB query, but maybe double-check)
        # chat_history = sorted(chat_history, key=lambda x: x.get("created_at"), reverse=False)
        logging.info(f"Found {len(chat_history)} previous messages in conversation history")
        
        # Generate AI response
        ai_response = generate_ai_response(
            message=user_message,
            search_results=search_results,
            profile_data=profile_data,
            chat_history=chat_history
        )
        
        logging.info(f"Generated AI response: {ai_response[:50]}...")
        
        # Log chat interaction using the new function
        logging.info(f"Saving chat message to conversation {conversation_id}...")
        try:
            log_chat_message(
                conversation_id=conversation_id,
                message=user_message,
                sender="user", 
                response=ai_response
            )
            logging.info("Chat message saved successfully.")
        except Exception as log_err:
            # Log error but continue to return response to user
            logger.error(f"Failed to log chat message: {log_err}") 
            logger.error(traceback.format_exc())
        
        # TODO: Update vector DB storage if needed
        # The add_conversation_to_vector_db function might need updating
        # to work with conversation_id or to fetch necessary context differently.
        # logging.info(f"Adding conversation turn to vector database for conversation {conversation_id}")
        # add_conversation_to_vector_db(...) 
        
        return models.ChatResponse(response=ai_response)
        
    except Exception as e:
        logger.error(f"Error processing chat: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# Get chat history endpoint - Updated to use conversation_id
# This endpoint needs a way to get the conversation_id. 
# Option 1: Frontend provides it directly (e.g., /conversations/{id}/history)
# Option 2: Frontend provides chatbot_id + visitor_id, backend looks up conversation_id.
# Implementing Option 2 for now, assuming frontend has chatbot_id and visitor_id.
@app.get("/chat/history")
async def history(chatbot_id: str, visitor_id: str, limit: int = 50):
    """Get chat history for a specific chatbot and visitor."""
    try:
        logger.info(f"Getting chat history for chatbot: {chatbot_id}, visitor: {visitor_id}, limit: {limit}")
        
        # Ensure visitor exists and get their UUID
        try:
            visitor_record = get_or_create_visitor(visitor_id)
            db_visitor_id = visitor_record.get("id") if visitor_record else visitor_id
            if not db_visitor_id:
                raise ValueError("Could not find visitor record")
            logger.info(f"Using visitor UUID: {db_visitor_id}")
        except Exception as visitor_err:
            logger.error(f"Failed to get visitor UUID for history: {visitor_err}")
            raise HTTPException(status_code=404, detail="Visitor not found")

        # Find the conversation ID
        try:
            # Use get_or_create, but we expect it to exist if history is requested
            conversation_id = get_or_create_conversation(chatbot_id=chatbot_id, visitor_id=str(db_visitor_id))
            logger.info(f"Found conversation_id: {conversation_id}")
        except ValueError as ve:
            logger.error(f"Value error finding conversation: {ve}")
            raise HTTPException(status_code=404, detail=f"Conversation not found: {ve}")
        except Exception as e:
            logger.error(f"Error finding conversation for history: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving conversation")

        # Get chat history using the conversation ID
        history_messages = get_chat_history(
            conversation_id=conversation_id,
            limit=limit
        )
        
        logging.info(f"Retrieved {len(history_messages)} chat history entries for conversation {conversation_id}")
        
        # Return history in the expected format (check if models.ChatHistoryResponse exists or adjust)
        # Assuming a simple list return for now
        return history_messages

    except HTTPException as he:
        raise he # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal Server Error retrieving history: {str(e)}")

# Add a direct route for public chatbot access by user ID
@app.get("/chat/{user_id}/public")
async def get_public_chatbot_by_user_id(user_id: str):
    """
    Public endpoint to get or create a chatbot for a user
    This is accessible without authentication
    """
    try:
        # Get or create a chatbot for the user
        chatbot = get_or_create_chatbot(user_id=user_id)
        
        if not chatbot:
            raise HTTPException(
                status_code=404, 
                detail=f"No chatbot found for user {user_id}"
            )
        
        # Return the chatbot data
        return chatbot
    except Exception as e:
        logging.error(f"Error getting public chatbot by user ID: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chatbot: {str(e)}"
        )

# Add a POST endpoint for public chatbot access by user ID
@app.post("/chat/{user_id}/public", response_model=ChatResponse)
async def public_chat(user_id: str, chat_request: ChatRequest):
    """
    Public endpoint to interact with a chatbot by user ID
    This endpoint first finds the chatbot associated with the user, then processes the request
    """
    try:
        # Extract the message from the last message in the messages array
        message = ""
        if chat_request.messages and len(chat_request.messages) > 0:
            message = chat_request.messages[-1].content
        
        visitor_id = chat_request.visitor_id
        visitor_name = chat_request.visitor_name
        
        logger.info(f"Public chat request for user ID: {user_id}, visitor ID: {visitor_id}")
        logger.info(f"Message content: {message[:50]}..." if len(message) > 50 else f"Message content: {message}")
        
        # Get the chatbot for this user - this will get or create a chatbot
        chatbot = get_or_create_chatbot(user_id=user_id)
        
        if not chatbot:
            raise HTTPException(
                status_code=404, 
                detail=f"No chatbot found for user {user_id}"
            )
            
        # Ensure the chatbot is public
        if not chatbot.get("is_public", True):
            raise HTTPException(
                status_code=403,
                detail="This chatbot is not publicly accessible"
            )
            
        # Get the actual chatbot ID to use
        chatbot_id = chatbot.get("id")
        logger.info(f"Using chatbot with ID: {chatbot_id} for public chat")
        
        # Get or create the visitor record
        visitor_record = get_or_create_visitor(visitor_id_text=visitor_id, name=visitor_name)
        if not visitor_record:
            raise HTTPException(
                status_code=500,
                detail="Failed to create or retrieve visitor record"
            )
            
        db_visitor_id = visitor_record.get("id")
        if not db_visitor_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to get visitor ID from record"
            )
            
        # Get or create the conversation
        conversation_id = get_or_create_conversation(
            chatbot_id=str(chatbot_id),
            visitor_id=str(db_visitor_id)
        )
        
        logger.info(f"Using conversation ID: {conversation_id} for chat")
        
        # Get profile data for the chatbot owner
        profile_data = get_profile_data(user_id=user_id)
        
        # Query vector database for relevant context
        search_results = query_vector_db(
            query=message, 
            n_results=3,
            user_id=user_id
        )
        
        # Get sequential conversation history
        chat_history = get_chat_history(
            conversation_id=conversation_id,
            limit=10
        )
        
        # Generate AI response
        ai_response = generate_ai_response(
            message=message,
            search_results=search_results,
            profile_data=profile_data,
            chat_history=chat_history
        )
        
        # Log the message and response to the database with the conversation ID
        log_chat_message(
            conversation_id=conversation_id,
            message=message,
            sender="user",
            response=ai_response
        )
        
        return ChatResponse(
            response=ai_response,
            chatbot_id=str(chatbot_id)
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in public chat endpoint: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat request: {str(e)}"
        )

# Add a GET endpoint for public chatbot history access by user ID
@app.get("/chat/{user_id}/public/history")
async def get_public_chatbot_history(user_id: str, visitor_id: Optional[str] = None, limit: int = 50):
    """
    Get chat history for a public chatbot by user ID
    This endpoint uses the user ID to find the associated chatbot, then retrieves the conversation
    """
    try:
        # Log the request details
        logger.info(f"Getting public chat history for user_id: {user_id}, visitor_id: {visitor_id}")
        
        # First, get the chatbot for this user (don't create if it doesn't exist)
        chatbot = get_or_create_chatbot(user_id=user_id)
        if not chatbot:
            raise HTTPException(
                status_code=404,
                detail=f"No chatbot found for user {user_id}"
            )
        
        # Ensure chatbot is public
        if not chatbot.get("is_public", True):
            raise HTTPException(
                status_code=403,
                detail="This chatbot is not publicly accessible"
            )
            
        # Now we have the actual chatbot ID to use
        chatbot_id = chatbot.get("id")
        logger.info(f"Found chatbot with ID: {chatbot_id} for user: {user_id}")
        
        # Verify visitor ID exists, create if needed
        if not visitor_id:
            logger.warning("No visitor_id provided, cannot retrieve chat history")
            return []
            
        try:
            # Find or create the visitor in our database
            db_visitor_id = get_or_create_visitor(visitor_id_text=visitor_id)
            logger.info(f"Found or created visitor with DB ID: {db_visitor_id}")
        except Exception as ve:
            logger.error(f"Error finding/creating visitor: {ve}")
            raise HTTPException(status_code=500, detail=f"Visitor error: {str(ve)}")

        # Find the conversation ID using chatbot_id and the visitor's DB UUID
        try:
            conversation_id = get_or_create_conversation(chatbot_id=str(chatbot_id), visitor_id=str(db_visitor_id))
            logger.info(f"Found conversation_id: {conversation_id} for public history")
        except ValueError as ve:
            logger.error(f"Value error finding public conversation: {ve}")
            raise HTTPException(status_code=404, detail=f"Conversation not found: {ve}")
        except Exception as e:
            logger.error(f"Error finding public conversation for history: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving conversation")

        # Get chat history using the conversation ID
        history_messages = get_chat_history(
            conversation_id=conversation_id,
            limit=limit
        )
        
        logging.info(f"Retrieved {len(history_messages)} public chat history entries for conversation {conversation_id}")
        
        # Return history as a simple list (matching the main /chat/history endpoint)
        return history_messages
        
    except HTTPException as he:
        raise he # Re-raise HTTP exceptions
    except Exception as e:
        logging.error(f"Error getting public chat history: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get public chat history: {str(e)}"
        )

# Add the emergency chat endpoint
@app.post("/emergency-chat", response_model=ChatResponse)
async def emergency_chat(request: Request):
    # Parse the request body manually
    body = await request.json()
    # Pass the request to the emergency endpoint
    return await emergency_chat_endpoint(body)

# Add a check endpoint to verify chat functionality
@app.get("/check-chat")
async def check_chat():
    return {"status": "ok", "emergency_mode": EMERGENCY_MODE}

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