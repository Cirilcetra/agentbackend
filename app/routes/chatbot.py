import time
import logging
import traceback
import uuid

from fastapi import APIRouter, HTTPException, Depends, Query, Request, Header, Cookie, status
from typing import List, Optional

from app import models
from app.database import (
    log_chat_message, get_chat_history, get_profile_data, 
    get_or_create_chatbot, supabase, get_or_create_conversation, get_or_create_visitor,
    get_user_chatbots, update_chatbot_config
)
from app.embeddings import query_vector_db, generate_ai_response, add_conversation_to_vector_db
from app.auth import get_current_user, User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/chat", response_model=models.ChatResponse)
async def chat(request: models.ChatRequest):
    """
    Handle a chat request from the frontend
    Updated to use conversation logic.
    """
    start_time = time.time()
    owner_user_id = None
    chatbot = None
    conversation_id = None

    try:
        # Get the user's message and visitor info
        message = request.message
        visitor_id = request.visitor_id
        visitor_name = request.visitor_name
        chatbot_id = request.chatbot_id
        
        logger.info(f"Chat request received from visitor {visitor_id} (name: {visitor_name or 'unknown'})")
        logger.info(f"Message: {message[:100]}..." if len(message) > 100 else f"Message: {message}")
        logger.info(f"Chatbot ID requested: {chatbot_id or 'None'}")
        
        # Basic input validation
        if not message or message.strip() == "":
            logger.warning("Empty message received")
            return models.ChatResponse(
                response="I didn't receive a message. Could you please try again?",
                query_time_ms=0
            )

        # --- Determine Chatbot and Owner --- 
        if not chatbot_id:
             # This case should theoretically not happen due to model validation
             logger.error("Chatbot ID is missing unexpectedly.")
             raise HTTPException(status_code=400, detail="Chatbot ID is required.")

        chatbot = get_or_create_chatbot(chatbot_id=chatbot_id)
        if not chatbot:
            raise HTTPException(status_code=404, detail=f"Chatbot not found: {chatbot_id}")
        owner_user_id = chatbot.get("user_id")
        chatbot_config = chatbot.get("configuration", {})
        logger.info(f"Using provided chatbot_id {chatbot_id} owned by user {owner_user_id}")
        
        if not owner_user_id:
             logger.error(f"Could not determine owner_user_id for chatbot {chatbot_id}")
             raise HTTPException(status_code=500, detail="Could not identify chatbot owner.")

        # --- Ensure Visitor and Conversation --- 
        if not visitor_id:
            visitor_id = str(uuid.uuid4())
            logger.warning(f"No visitor_id provided, generated a new one: {visitor_id}")

        try:
            visitor_record = get_or_create_visitor(visitor_id, visitor_name)
            db_visitor_id = visitor_record.get('id') if visitor_record else visitor_id
            if not db_visitor_id:
                 logger.error(f"Failed to get or create visitor, using original ID: {visitor_id}")
                 db_visitor_id = visitor_id 
            else:
                 logger.info(f"Ensured visitor exists with UUID: {db_visitor_id}")
                 # Use the db_visitor_id (UUID) going forward
                 visitor_id = str(db_visitor_id) 
        except Exception as visitor_err:
            logger.error(f"Error ensuring visitor exists: {visitor_err}")
            raise HTTPException(status_code=500, detail=f"Failed to process visitor information: {visitor_err}")

        try:
             conversation_id = get_or_create_conversation(chatbot_id=str(chatbot_id), visitor_id=visitor_id) # Use UUID visitor_id
             logger.info(f"Using conversation_id: {conversation_id}")
        except Exception as conv_err:
             logger.error(f"Error getting/creating conversation: {conv_err}")
             raise HTTPException(status_code=500, detail=f"Failed to establish conversation: {conv_err}")

        # --- Profile Data --- 
        profile_data = get_profile_data(user_id=owner_user_id)
        if profile_data:
            profile_id = profile_data.get('id', 'None')
            logger.info(f"Loaded profile data for chatbot owner (user_id={owner_user_id}): profile_id={profile_id}")
        else:
            logger.warning(f"No profile data found for chatbot owner (user_id={owner_user_id}) - using empty profile")
            profile_data = {}
        
        # --- Vector DB Search --- 
        logger.info(f"Querying vector DB for relevant context for conversation {conversation_id}")
        search_results = query_vector_db(
            query=message, 
            n_results=3,
            user_id=owner_user_id,
            # visitor_id=visitor_id, # Maybe filter by visitor?
            # include_conversation=True # Needs review based on vector storage changes
        )
        
        # --- Database Chat History --- 
        logger.info(f"Fetching sequential conversation history for conversation {conversation_id}")
        history_limit = 10
        chat_history = get_chat_history(
            conversation_id=conversation_id,
            limit=history_limit 
            # REMOVED: visitor_id, chatbot_id
        )
        
        logger.info(f"Found {len(chat_history)} previous messages in conversation history")
        
        # --- Generate AI Response --- 
        logger.info(f"Generating AI response with conversation context")
        ai_response = await generate_ai_response(
            message=message,
            search_results=search_results,
            profile_data=profile_data,
            chat_history=chat_history,
            chatbot_config=chatbot_config
        )
        
        if not ai_response or ai_response.strip() == "":
            logger.warning("Empty response from AI - using fallback")
            ai_response = "I apologize, but I couldn't formulate a proper response. Could we try a different question?"
        
        # --- Log Message --- 
        logger.info(f"Logging chat message to conversation {conversation_id}")
        try:
            log_result = log_chat_message(
                conversation_id=conversation_id,
                message=message, 
                sender="user", 
                response=ai_response,
                metadata={} # Add metadata if available/needed
                # REMOVED: visitor_id, visitor_name, target_user_id, chatbot_id
            )
            logger.info("Message logged successfully.")
        except Exception as log_err:
             logger.error(f"Failed to log chat message (continuing): {log_err}")
             logger.error(traceback.format_exc())

        # --- Update Vector DB (TODO) --- 
        # message_id = log_result[0]["id"] if log_result and len(log_result) > 0 else None # Need to get message_id if logging succeeded
        # logger.info(f"Adding conversation turn to vector database for conversation {conversation_id}")
        # add_conversation_to_vector_db(...)
        
        # --- Calculate Time and Return --- 
        end_time = time.time()
        query_time_ms = (end_time - start_time) * 1000
        logger.info(f"Request completed in {query_time_ms:.0f}ms")
        
        return models.ChatResponse(
            response=ai_response,
            query_time_ms=query_time_ms
        )
    
    # --- Error Handling Fallback --- 
    except Exception as e:
        logger.error(f"Error in chat route: {str(e)}")
        logger.error(traceback.format_exc())
        # Log the error, but still try to return a reasonable response
        try:
            profile_data_fallback = {}
            
            # Try to get minimal profile data if possible
            try:
                if owner_user_id: # Check if owner_user_id was determined before error
                    profile_data_fallback = get_profile_data(user_id=owner_user_id)
                    logger.info(f"Retrieved fallback profile for error recovery: {profile_data_fallback.get('id', 'None')}")
            except Exception as profile_error:
                logger.error(f"Error getting profile data for fallback: {str(profile_error)}")
            
            # Generate a basic response without vector DB or history
            fallback_response = "I'm sorry, I encountered an error processing your request. Please try again."
            
            # Try to generate a slightly better response if we have profile data
            if profile_data_fallback:
                try:
                    fallback_response = await generate_ai_response(
                        message=request.message if request else "",
                        search_results={"documents": [], "metadatas": [], "distances": []},
                        profile_data=profile_data_fallback,
                        chat_history=[]
                    )
                    logger.info("Generated fallback AI response after error")
                except Exception as ai_error:
                    logger.error(f"Error generating fallback AI response: {str(ai_error)}")
            
            # Try to log the incoming message with the error response
            try:
                 if conversation_id: # Only log if we managed to get a conversation ID
                     log_chat_message(
                         conversation_id=conversation_id,
                         message=request.message if request else "[Original message unavailable]", 
                         sender="user", 
                         response=fallback_response, 
                         metadata={"error": str(e)} # Log the error in metadata
                     )
                     logger.info("Logged failed request attempt to conversation.")
                 else:
                     logger.warning("Cannot log failed request as conversation_id was not determined.")
            except Exception as log_fallback_error:
                logger.error(f"Error logging failed request: {str(log_fallback_error)}")

            # Calculate time for error handling
            end_time = time.time()
            query_time_ms = (end_time - start_time) * 1000
            logger.info(f"Error recovery completed in {query_time_ms:.0f}ms")
            
            # Return the fallback response
            return models.ChatResponse(
                response=fallback_response,
                query_time_ms=query_time_ms
            )
            
        except Exception as fallback_exception:
            # If even the fallback fails, log it and raise the original exception
            logger.error(f"Critical error in fallback handling: {str(fallback_exception)}")
            logger.error(traceback.format_exc())
        
        # Re-raise the original exception if fallback logging failed
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat request: {str(e)}"
        )

@router.get("/history", response_model=models.ChatHistoryResponse)
async def get_chat_history_endpoint(
    # Updated: Expect chatbot_id and visitor_id, use them to find conversation_id
    chatbot_id: str = Query(..., description="The ID of the chatbot"),
    visitor_id: str = Query(..., description="The ID of the visitor"),
    limit: int = Query(50, description="Maximum number of messages to return"), 
    current_user: Optional[User] = Depends(get_current_user) # Keep auth check if needed
):
    """
    Get chat history for a specific chatbot and visitor.
    Updated to use conversation logic.
    """
    try:
        logger.info(f"Getting chat history for chatbot {chatbot_id}, visitor {visitor_id}")

        # --- Authentication/Authorization Check (Optional) ---
        # If you need to ensure the current_user owns the chatbot_id
        # if current_user:
        #     chatbot_check = get_or_create_chatbot(chatbot_id=chatbot_id)
        #     if not chatbot_check or chatbot_check.get("user_id") != current_user.id:
        #         raise HTTPException(status_code=403, detail="Forbidden: Access denied to this chatbot history")
        # else: # If no user, assume public access is allowed based on RLS
        #     pass 

        # --- Ensure Visitor and Get Conversation ID --- 
        try:
            visitor_record = get_or_create_visitor(visitor_id)
            db_visitor_id = visitor_record.get('id') if visitor_record else visitor_id
            if not db_visitor_id:
                raise ValueError("Could not find or resolve visitor record")
            logger.info(f"Using visitor UUID {db_visitor_id} for history lookup")
            visitor_id = str(db_visitor_id) # Use the UUID from now on
        except Exception as visitor_err:
            logger.error(f"Failed to get visitor UUID for history: {visitor_err}")
            raise HTTPException(status_code=404, detail=f"Visitor not found: {visitor_id}")

        try:
            conversation_id = get_or_create_conversation(chatbot_id=chatbot_id, visitor_id=visitor_id)
            logger.info(f"Found conversation_id: {conversation_id} for history")
        except ValueError as ve:
             logger.error(f"Value error finding conversation for history: {ve}")
             raise HTTPException(status_code=404, detail=f"Conversation not found: {ve}")
        except Exception as e:
             logger.error(f"Error finding conversation for history: {e}")
             raise HTTPException(status_code=500, detail="Error retrieving conversation")

        # --- Fetch History --- 
        history_messages = get_chat_history(
            conversation_id=conversation_id,
            limit=limit
        )
        
        logging.info(f"Retrieved {len(history_messages)} messages for conversation {conversation_id}")

        # --- Format Response --- 
        # The backend DB function now returns a list of message dicts.
        # Format them into the ChatHistoryItem model expected by the frontend/response_model.
        formatted_history: List[models.ChatHistoryItem] = []
        for item in history_messages:
             formatted_history.append(models.ChatHistoryItem(
                 id=item.get("id", ""),
                 message=item.get("message", ""),
                 sender=item.get("sender", "user"),
                 response=item.get("response"),
                 visitor_id=item.get("visitor_id"), # Keep original visitor_id if needed by frontend? Check model
                 timestamp=item.get("created_at") or item.get("timestamp"), # Prefer created_at
                 conversation_id=item.get("conversation_id"), # Add conversation_id
                 # Add other fields from message table if needed by ChatHistoryItem model
             ))
        
        # Return using the response_model
        return models.ChatHistoryResponse(
            history=formatted_history,
            count=len(formatted_history)
        )

    except HTTPException as he:
        raise he # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error in get_chat_history_endpoint: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal Server Error retrieving history")

@router.get("/chatbots", response_model=List[models.ChatbotModel])
async def get_chatbots(current_user: User = Depends(get_current_user)):
    """
    Get all chatbots for the authenticated user
    """
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")

        logger.info(f"Fetching chatbots for authenticated user: {current_user.id}")
        chatbots = get_user_chatbots(user_id=current_user.id)

        if chatbots is None: # Check if function returned None due to error
            logger.error(f"Database function get_user_chatbots returned None for user {current_user.id}")
            raise HTTPException(status_code=500, detail="Failed to retrieve chatbots from database.")

        # Convert the list of dicts to a list of ChatbotModel instances
        # The response_model=List[models.ChatbotModel] handles the validation
        return chatbots

    except Exception as e:
        logger.error(f"Error getting chatbots: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chatbots: {str(e)}"
        )

@router.put("/chatbots/{chatbot_id}", response_model=models.ChatbotModel)
async def update_chatbot(
    chatbot_id: str,
    update_data: models.ChatbotUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Update a chatbot's configuration (e.g., tone, personality).
    Requires authentication.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    # Assuming update_data.configuration holds the settings dictionary
    if update_data.configuration is None:
         raise HTTPException(status_code=400, detail="Configuration data is required for update.")
         
    try:
        logger.info(f"Attempting to update chatbot {chatbot_id} for user {current_user.id}")
        
        # Log the public_url_slug if provided
        if update_data.public_url_slug is not None:
            logger.info(f"Received public_url_slug update: {update_data.public_url_slug}")
        
        updated_chatbot = update_chatbot_config(
            chatbot_id=chatbot_id,
            configuration=update_data.configuration,
            user_id=current_user.id,
            public_url_slug=update_data.public_url_slug
        )
        
        if updated_chatbot:
            return updated_chatbot
        else:
            # Check if chatbot exists but belongs to another user or if update failed
            # You might want more specific error handling based on update_chatbot_config return
            raise HTTPException(status_code=404, detail=f"Chatbot not found or update failed for ID: {chatbot_id}")
            
    except Exception as e:
        logger.error(f"Error updating chatbot {chatbot_id}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update chatbot: {str(e)}"
        )

@router.get("/chat/{user_id}/public", response_model=models.ChatbotModel)
async def get_public_chatbot_by_user_id(user_id: str):
    """
    Get a chatbot by user ID for public access (no authentication required)
    """
    try:
        # Get or create a chatbot for the specified user
        chatbot = get_or_create_chatbot(user_id=user_id)
        
        if not chatbot:
            raise HTTPException(
                status_code=404,
                detail=f"No chatbot found for user {user_id}"
            )
        
        # Ensure it's marked as public
        if not chatbot.get("is_public", True):
            raise HTTPException(
                status_code=403,
                detail="This chatbot is not publicly accessible"
            )
        
        return chatbot
    except Exception as e:
        logger.error(f"Error getting public chatbot by user ID: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chatbot: {str(e)}"
        )

@router.post("/chat/{user_id}/public", response_model=models.ChatResponse)
async def chat_with_public_chatbot(user_id: str, request: models.ChatRequest):
    """
    Send a message to a chatbot by user ID for public access (no authentication required)
    """
    start_time = time.time()
    
    try:
        # Get the user's message and visitor info
        message = request.message
        visitor_id = request.visitor_id
        visitor_name = request.visitor_name
        
        # Add detailed logging
        logger.info(f"Public chat request for user_id {user_id} from visitor {visitor_id} (name: {visitor_name or 'unknown'})")
        logger.info(f"Message: {message[:100]}..." if len(message) > 100 else f"Message: {message}")
        
        # Basic input validation
        if not message or message.strip() == "":
            logger.warning("Empty message received")
            return models.ChatResponse(
                response="I didn't receive a message. Could you please try again?",
                query_time_ms=0
            )
        
        # Get or create the chatbot for this user
        chatbot = get_or_create_chatbot(user_id=user_id)
        if not chatbot:
            raise HTTPException(status_code=404, detail=f"No chatbot found for user {user_id}")
        
        # Ensure it's marked as public
        if not chatbot.get("is_public", True):
            raise HTTPException(
                status_code=403,
                detail="This chatbot is not publicly accessible"
            )
        
        # We know the owner's user_id is the user_id from the path
        owner_user_id = user_id
        logger.info(f"Using chatbot owned by user_id: {owner_user_id}")
        
        # Always get the profile data for the chatbot OWNER
        profile_data = get_profile_data(user_id=owner_user_id)
        if profile_data:
            profile_id = profile_data.get('id', 'None')
            logger.info(f"Loaded profile data for chatbot owner (user_id={owner_user_id}): profile_id={profile_id}")
        else:
            logger.warning(f"No profile data found for chatbot owner (user_id={owner_user_id}) - using empty profile")
            profile_data = {}
        
        # Create or get visitor record
        visitor_record = get_or_create_visitor(visitor_id, visitor_name)
        if not visitor_record:
            raise HTTPException(status_code=500, detail="Failed to create or retrieve visitor record")
            
        db_visitor_id = visitor_record.get("id")
        if not db_visitor_id:
            raise HTTPException(status_code=500, detail="Failed to get visitor ID from record")
        
        # Get or create the conversation
        conversation_id = get_or_create_conversation(
            chatbot_id=str(chatbot["id"]),
            visitor_id=str(db_visitor_id)
        )
        logger.info(f"Using conversation ID: {conversation_id} for chat")
        
        # Get context for the AI by searching vector DB, including relevant conversation history
        logger.info(f"Querying vector DB for relevant context and conversation history with user_id: {owner_user_id}")
        search_results = query_vector_db(
            query=message, 
            user_id=owner_user_id,  # Pass the chatbot owner's user_id explicitly
            visitor_id=visitor_id,
            include_conversation=True
        )
        
        # Get recent conversation history for this conversation
        logger.info(f"Fetching sequential conversation history for conversation {conversation_id}")
        history_limit = 10  # Get the last 10 messages (5 exchanges)
        chat_history = get_chat_history(
            conversation_id=conversation_id,
            limit=history_limit
        )
        
        # Sort the history by timestamp (oldest first)
        if chat_history:
            chat_history = sorted(
                chat_history,
                key=lambda x: x.get("created_at", "") or x.get("timestamp", ""),
                reverse=False  # Oldest messages first
            )
            logger.info(f"Found {len(chat_history)} previous messages in conversation history")
        else:
            logger.info("No previous conversation history found")
            chat_history = []
        
        # Generate the AI response
        logger.info(f"Generating AI response with conversation context")
        ai_response = await generate_ai_response(
            message=message,
            search_results=search_results,
            profile_data=profile_data,
            chat_history=chat_history,
            chatbot_config=chatbot.get("configuration", {})
        )
        
        # Brief validation of the response
        if not ai_response or ai_response.strip() == "":
            logger.warning("Empty response from AI - using fallback")
            ai_response = "I apologize, but I couldn't formulate a proper response. Could we try a different question?"
        
        # Log the message to the database
        logger.info(f"Logging chat message to database")
        log_result = log_chat_message(
            conversation_id=conversation_id,
            message=message, 
            sender="user", 
            response=ai_response
        )
        
        # Also store this conversation exchange in the vector database for semantic search
        message_id = None
        if log_result and isinstance(log_result, list) and len(log_result) > 0 and isinstance(log_result[0], dict):
            message_id = log_result[0].get("id")

        if message_id:
            logger.info(f"Adding conversation to vector database for future reference with user_id: {owner_user_id}")
            add_conversation_to_vector_db(
                message=message,
                response=ai_response,
                visitor_id=visitor_id,
                message_id=message_id,
                user_id=owner_user_id  # Pass the chatbot owner's user_id
            )
        else:
            logger.warning("Could not add conversation to vector DB: Failed to get message_id from log_result.")

        # Calculate time taken
        end_time = time.time()
        query_time_ms = (end_time - start_time) * 1000
        logger.info(f"Public request completed in {query_time_ms:.0f}ms")
        
        return models.ChatResponse(
            response=ai_response,
            query_time_ms=query_time_ms
        )
    
    except Exception as e:
        # Ensure logger is available in this scope
        import logging
        import traceback
        # logger = logging.getLogger(__name__) # <-- REMOVE THIS LINE. Use module-level logger.

        logger.error(f"Error in public chat route: {str(e)}")
        logger.error(traceback.format_exc()) # Log the full traceback
        
        # Raise HTTPException to return a proper 500 error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error processing chat: {str(e)}"
        )

@router.get("/chat/{user_id}/public/history", response_model=models.ChatHistoryResponse)
async def get_public_chat_history(
    user_id: str,
    visitor_id: Optional[str] = Query(None, description="Filter chat history by visitor ID"),
    limit: int = Query(50, description="Maximum number of messages to return")
):
    """
    Get chat history for a public chatbot by user ID (no authentication required)
    """
    try:
        # Log the request details
        logger.info(f"Getting public chat history for user_id: {user_id}, visitor_id: {visitor_id}")
        
        # Get the chatbot for this user
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
        
        if not supabase:
            logger.error("Supabase client not initialized")
            return models.ChatHistoryResponse(history=[], count=0)
        
        if not visitor_id:
            logger.warning("No visitor_id provided, cannot retrieve chat history")
            return models.ChatHistoryResponse(history=[], count=0)
        
        # Get or create visitor record
        try:
            visitor_record = get_or_create_visitor(visitor_id)
            db_visitor_id = visitor_record.get("id") 
            if not db_visitor_id:
                logger.error("Failed to get visitor ID from record")
                return models.ChatHistoryResponse(history=[], count=0)
        except Exception as ve:
            logger.error(f"Error finding/creating visitor: {ve}")
            raise HTTPException(status_code=500, detail=f"Visitor error: {str(ve)}")

        # Find the conversation ID using chatbot_id and visitor's DB UUID
        try:
            conversation_id = get_or_create_conversation(
                chatbot_id=str(chatbot["id"]), 
                visitor_id=str(db_visitor_id)
            )
            logger.info(f"Found conversation_id: {conversation_id} for public history")
        except ValueError as ve:
            logger.error(f"Value error finding public conversation: {ve}")
            raise HTTPException(status_code=404, detail=f"Conversation not found: {ve}")
        except Exception as e:
            logger.error(f"Error finding public conversation for history: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving conversation")

        # Get chat history using the conversation ID
        history = get_chat_history(
            conversation_id=conversation_id,
            limit=limit
        )
        
        # Convert the history to the expected format
        formatted_history = []
        for item in history:
            # Create a standardized history item
            formatted_item = {
                "id": item.get("id", ""),
                "message": item.get("message", ""),
                "sender": item.get("sender", "user"),
                "response": item.get("response"),
                "visitor_id": visitor_id,  # Use the original visitor_id for consistency
                "visitor_name": visitor_record.get("name"),
                "timestamp": item.get("created_at") or item.get("timestamp", "")
            }
            formatted_history.append(models.ChatHistoryItem(**formatted_item))
        
        response = models.ChatHistoryResponse(
            history=formatted_history,
            count=len(formatted_history)
        )
        
        logger.info(f"Returning public chat history with {len(formatted_history)} items")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting public chat history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get public chat history: {str(e)}"
        ) 