import time
import logging
from fastapi import APIRouter, HTTPException, Depends, Query, Request, Header, Cookie
from typing import List, Optional

from app import models
from app.database import log_chat_message, get_chat_history, get_profile_data, get_or_create_chatbot, supabase
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
    """
    start_time = time.time()
    
    try:
        # Get the user's message and visitor info
        message = request.message
        visitor_id = request.visitor_id
        visitor_name = request.visitor_name
        chatbot_id = request.chatbot_id
        
        # Add more detailed logging
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
        
        # Get the chatbot by ID or create a default one if not specified
        chatbot = None
        owner_user_id = None
        
        if chatbot_id:
            # Always use the exact chatbot ID provided in the request
            chatbot = get_or_create_chatbot(chatbot_id=chatbot_id)
            if not chatbot:
                raise HTTPException(status_code=404, detail="Chatbot not found")
            
            # Get the owner's user_id
            owner_user_id = chatbot.get("user_id")
            logger.info(f"Using chatbot with ID {chatbot_id} owned by user_id: {owner_user_id}")
        else:
            # If no chatbot_id specified, use the default chatbot
            chatbot = get_or_create_chatbot()
            if chatbot:
                owner_user_id = chatbot.get("user_id")
                logger.info(f"Using default chatbot owned by user_id: {owner_user_id}")
            else:
                logger.error("No default chatbot found and no chatbot_id provided")
                raise HTTPException(status_code=404, detail="No chatbot found")
        
        # Always get the profile data for the chatbot OWNER (not the visiting user)
        if owner_user_id:
            profile_data = get_profile_data(user_id=owner_user_id)
            if profile_data:
                profile_id = profile_data.get('id', 'None')
                logger.info(f"Loaded profile data for chatbot owner (user_id={owner_user_id}): profile_id={profile_id}")
            else:
                logger.warning(f"No profile data found for chatbot owner (user_id={owner_user_id}) - using empty profile")
                profile_data = {}
        else:
            logger.warning("No owner_user_id found for the chatbot - using empty profile")
            profile_data = {}
        
        # Get context for the AI by searching vector DB, including relevant conversation history
        logger.info(f"Querying vector DB for relevant context and conversation history with user_id: {owner_user_id}")
        search_results = query_vector_db(
            query=message, 
            user_id=owner_user_id,  # Pass the chatbot owner's user_id explicitly
            visitor_id=visitor_id,
            include_conversation=True
        )
        
        # Get recent conversation history for this visitor (limit to last 5 messages) from database
        logger.info(f"Fetching sequential conversation history for visitor {visitor_id}")
        history_limit = 10  # Get the last 10 messages (5 exchanges)
        chat_history = get_chat_history(
            limit=history_limit, 
            visitor_id=visitor_id,
            chatbot_id=chatbot["id"] if chatbot else None
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
            chat_history=chat_history
        )
        
        # Brief validation of the response
        if not ai_response or ai_response.strip() == "":
            logger.warning("Empty response from AI - using fallback")
            ai_response = "I apologize, but I couldn't formulate a proper response. Could we try a different question?"
        
        # Log the message to the database
        logger.info(f"Logging chat message to database")
        if chatbot:
            log_result = log_chat_message(
                message=message, 
                sender="user", 
                response=ai_response, 
                visitor_id=visitor_id, 
                visitor_name=visitor_name,
                target_user_id=owner_user_id,  # Use the chatbot owner's user_id
                chatbot_id=chatbot.get("id")
            )
        else:
            log_result = log_chat_message(
                message=message, 
                sender="user", 
                response=ai_response, 
                visitor_id=visitor_id, 
                visitor_name=visitor_name
            )
        
        # Also store this conversation exchange in the vector database for semantic search
        message_id = log_result[0]["id"] if log_result and len(log_result) > 0 else None
        logger.info(f"Adding conversation to vector database for future reference with user_id: {owner_user_id}")
        add_conversation_to_vector_db(
            message=message,
            response=ai_response,
            visitor_id=visitor_id,
            message_id=message_id,
            user_id=owner_user_id  # Pass the chatbot owner's user_id
        )
        
        # Calculate time taken
        end_time = time.time()
        query_time_ms = (end_time - start_time) * 1000
        logger.info(f"Request completed in {query_time_ms:.0f}ms")
        
        return models.ChatResponse(
            response=ai_response,
            query_time_ms=query_time_ms
        )
    
    except Exception as e:
        logger.error(f"Error in chat route: {str(e)}")
        # Log the error, but still try to return a reasonable response
        try:
            # Check if we can still process the chat without vector DB results
            profile_data = {}
            chat_history = []
            
            # Try to get minimal profile data if possible
            try:
                if 'owner_user_id' in locals() and owner_user_id:
                    profile_data = get_profile_data(user_id=owner_user_id)
                    logger.info(f"Retrieved fallback profile for error recovery: {profile_data.get('id', 'None')}")
            except Exception as profile_error:
                logger.error(f"Error getting profile data for fallback: {str(profile_error)}")
            
            # Generate a basic response without vector DB
            ai_response = "I'm sorry, I encountered an error processing your request. Please try again."
            
            # Try to generate a response if we at least have profile data
            if profile_data:
                try:
                    ai_response = await generate_ai_response(
                        message=request.message,
                        search_results={"documents": [], "metadatas": [], "distances": []},
                        profile_data=profile_data,
                        chat_history=[]
                    )
                    logger.info("Generated fallback AI response after error")
                except Exception as ai_error:
                    logger.error(f"Error generating fallback AI response: {str(ai_error)}")
            
            # Try to log the chat message even if there was an error
            log_chat_message(
                message=request.message, 
                sender="user", 
                response=ai_response, 
                visitor_id=request.visitor_id, 
                visitor_name=request.visitor_name,
                target_user_id=owner_user_id if 'owner_user_id' in locals() else None,
                chatbot_id=chatbot["id"] if 'chatbot' in locals() and chatbot else None
            )
            
            # Calculate the time for logging
            end_time = time.time()
            query_time_ms = (end_time - start_time) * 1000
            logger.info(f"Error recovery completed in {query_time_ms:.0f}ms")
            
            # Return the fallback response directly
            return models.ChatResponse(
                response=ai_response,
                query_time_ms=query_time_ms
            )
            
        except Exception as log_error:
            logger.error(f"Error in fallback handling: {str(log_error)}")
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat request: {str(e)}"
        )

@router.get("/history", response_model=models.ChatHistoryResponse)
async def get_chat_history_endpoint(
    limit: int = 50, 
    visitor_id: Optional[str] = Query(None, description="Filter chat history by visitor ID"),
    chatbot_id: Optional[str] = Query(None, description="Filter chat history by chatbot ID"),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Get chat history, optionally filtered by visitor ID and/or chatbot ID
    """
    try:
        # Filter by chatbot if specified
        if chatbot_id:
            # Verify the user has access to this chatbot if authenticated
            if current_user:
                chatbot = get_or_create_chatbot(chatbot_id=chatbot_id)
                if chatbot and chatbot.get("user_id") != current_user.id:
                    # Only allow the owner to access the full chatbot history
                    if not visitor_id:
                        raise HTTPException(
                            status_code=403, 
                            detail="You can only access your own chatbots' history"
                        )
        
        # If Supabase is available, query directly with visitor_id_text
        if supabase and visitor_id:
            try:
                # Set up the base query
                if chatbot_id:
                    query = supabase.table("messages").select("*").eq("chatbot_id", chatbot_id)
                else:
                    # If we're authenticated, get all messages for chatbots owned by the user
                    if current_user:
                        # First find all chatbots owned by the user
                        chatbot_response = supabase.table("chatbots").select("id").eq("user_id", current_user.id).execute()
                        if chatbot_response.data and len(chatbot_response.data) > 0:
                            # Get all chatbot IDs
                            chatbot_ids = [c["id"] for c in chatbot_response.data]
                            # Start with an empty query
                            query = supabase.table("messages").select("*")
                            # We'll add an OR condition for each chatbot
                            if len(chatbot_ids) == 1:
                                query = query.eq("chatbot_id", chatbot_ids[0])
                            else:
                                # Use 'in' filter if supported, otherwise chain OR conditions
                                query = query.in_("chatbot_id", chatbot_ids)
                        else:
                            # No chatbots found, so return empty result
                            return models.ChatHistoryResponse(history=[], count=0)
                    else:
                        # Not authenticated and no chatbot ID specified
                        query = supabase.table("messages").select("*")
                
                # Add visitor_id_text filter if visitor_id is provided
                if visitor_id:
                    query = query.eq("visitor_id_text", visitor_id)
                
                # Apply limit and ordering
                query = query.order("created_at", desc=True).limit(limit)
                response = query.execute()
                
                # Extract the history from the response
                history = response.data if response.data else []
                logger.info(f"Retrieved {len(history)} chat history items using direct query")
            except Exception as db_error:
                logger.error(f"Error querying chat history from Supabase: {db_error}")
                history = []
        else:
            # Fall back to the regular get_chat_history function
            history = get_chat_history(
                limit=limit, 
                visitor_id=visitor_id, 
                chatbot_id=chatbot_id
            )
            
            logger.info(f"Retrieved {len(history)} chat history items using get_chat_history")
        
        # Convert the history to the expected format
        formatted_history = []
        for item in history:
            # Create a standardized history item regardless of data source
            formatted_item = {
                "id": item.get("id", ""),
                "message": item.get("message", ""),
                "sender": item.get("sender", "user"),
                "response": item.get("response"),
                "visitor_id": item.get("visitor_id_text", "") or item.get("visitor_id", ""),  # Try visitor_id_text first
                "visitor_name": item.get("visitor_name"),
                "timestamp": item.get("created_at") or item.get("timestamp", "")
            }
            formatted_history.append(models.ChatHistoryItem(**formatted_item))
        
        response = models.ChatHistoryResponse(
            history=formatted_history,
            count=len(formatted_history)
        )
        
        logger.info(f"Returning response with {len(formatted_history)} items")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chat history: {str(e)}"
        )

@router.get("/chatbots", response_model=List[models.ChatbotModel])
async def get_chatbots(current_user: User = Depends(get_current_user)):
    """
    Get all chatbots for the authenticated user
    """
    try:
        # Query all chatbots for the current user
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # This will be implemented in the database.py file
        # For now, stub implementation
        chatbots = []
        return chatbots
    except Exception as e:
        logger.error(f"Error getting chatbots: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chatbots: {str(e)}"
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
        
        # Get context for the AI by searching vector DB, including relevant conversation history
        logger.info(f"Querying vector DB for relevant context and conversation history with user_id: {owner_user_id}")
        search_results = query_vector_db(
            query=message, 
            user_id=owner_user_id,  # Pass the chatbot owner's user_id explicitly
            visitor_id=visitor_id,
            include_conversation=True
        )
        
        # Get recent conversation history for this visitor
        logger.info(f"Fetching sequential conversation history for visitor {visitor_id}")
        history_limit = 10  # Get the last 10 messages (5 exchanges)
        chat_history = get_chat_history(
            limit=history_limit, 
            visitor_id=visitor_id,
            chatbot_id=chatbot["id"]
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
            chat_history=chat_history
        )
        
        # Brief validation of the response
        if not ai_response or ai_response.strip() == "":
            logger.warning("Empty response from AI - using fallback")
            ai_response = "I apologize, but I couldn't formulate a proper response. Could we try a different question?"
        
        # Log the message to the database
        logger.info(f"Logging chat message to database")
        log_result = log_chat_message(
            message=message, 
            sender="user", 
            response=ai_response, 
            visitor_id=visitor_id, 
            visitor_name=visitor_name,
            target_user_id=owner_user_id,  # Use the chatbot owner's user_id
            chatbot_id=chatbot.get("id")
        )
        
        # Also store this conversation exchange in the vector database for semantic search
        message_id = log_result[0]["id"] if log_result and len(log_result) > 0 else None
        logger.info(f"Adding conversation to vector database for future reference with user_id: {owner_user_id}")
        add_conversation_to_vector_db(
            message=message,
            response=ai_response,
            visitor_id=visitor_id,
            message_id=message_id,
            user_id=owner_user_id  # Pass the chatbot owner's user_id
        )
        
        # Calculate time taken
        end_time = time.time()
        query_time_ms = (end_time - start_time) * 1000
        logger.info(f"Public request completed in {query_time_ms:.0f}ms")
        
        return models.ChatResponse(
            response=ai_response,
            query_time_ms=query_time_ms
        )
    
    except Exception as e:
        logger.error(f"Error in public chat route: {str(e)}")
        try:
            # Generate a basic response without vector DB if possible
            if 'profile_data' in locals() and profile_data:
                try:
                    ai_response = await generate_ai_response(
                        message=request.message,
                        search_results={"documents": [], "metadatas": [], "distances": []},
                        profile_data=profile_data,
                        chat_history=[]
                    )
                    logger.info("Generated fallback AI response after error")
                    
                    # Save the fallback response to the database
                    log_result = log_chat_message(
                        message=request.message, 
                        sender="user", 
                        response=ai_response, 
                        visitor_id=visitor_id, 
                        visitor_name=visitor_name,
                        target_user_id=owner_user_id,
                        chatbot_id=chatbot.get("id")
                    )
                    
                    # Add to vector DB if possible
                    try:
                        message_id = log_result[0]["id"] if log_result and len(log_result) > 0 else None
                        add_conversation_to_vector_db(
                            message=request.message,
                            response=ai_response,
                            visitor_id=visitor_id,
                            message_id=message_id,
                            user_id=owner_user_id
                        )
                    except Exception as vector_error:
                        logger.error(f"Error adding fallback response to vector DB: {str(vector_error)}")
                    
                    return models.ChatResponse(
                        response=ai_response,
                        query_time_ms=(time.time() - start_time) * 1000
                    )
                except Exception as ai_error:
                    logger.error(f"Error generating fallback AI response: {str(ai_error)}")
        except Exception as fallback_error:
            logger.error(f"Error in fallback response: {str(fallback_error)}")
        
        # Return a generic error message as a last resort
        return models.ChatResponse(
            response="I'm sorry, I encountered an error processing your request. Please try again.",
            query_time_ms=0
        )

@router.get("/chat/{user_id}/public/history", response_model=models.ChatHistoryResponse)
async def get_public_chat_history(
    user_id: str,
    visitor_id: Optional[str] = Query(None, description="Filter chat history by visitor ID"),
    limit: int = Query(50, description="Maximum number of messages to return")
):
    """
    Get chat history for a public chatbot by user ID (no authentication required)
    This uses visitor_id_text directly instead of trying to join with visitors table
    """
    try:
        # Log the request details
        logger.info(f"Getting public chat history for user_id: {user_id}, visitor_id: {visitor_id}, chatbot_id: None")
        
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
        
        # Direct query using visitor_id_text instead of visitor_id
        try:
            query = supabase.table("messages").select("*").eq("chatbot_id", chatbot["id"])
            
            # Filter by visitor_id_text if provided
            if visitor_id:
                query = query.eq("visitor_id_text", visitor_id)
                
            # Apply limit and ordering
            query = query.order("created_at", desc=True).limit(limit)
            response = query.execute()
            
            history = response.data if response.data else []
            logger.info(f"Retrieved {len(history)} chat history entries")
        except Exception as db_error:
            logger.error(f"Error querying chat history from Supabase: {db_error}")
            history = []
        
        # Convert the history to the expected format
        formatted_history = []
        for item in history:
            # Create a standardized history item
            formatted_item = {
                "id": item.get("id", ""),
                "message": item.get("message", ""),
                "sender": item.get("sender", "user"),
                "response": item.get("response"),
                "visitor_id": item.get("visitor_id_text", ""),  # Use visitor_id_text
                "visitor_name": item.get("visitor_name"),
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