import time
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional

from app import models
from app.database import log_chat_message, get_chat_history, get_profile_data
from app.embeddings import query_vector_db, generate_ai_response, add_conversation_to_vector_db

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
        target_user_id = request.target_user_id  # Access directly from the model
        
        # Add more detailed logging
        print(f"[INFO] Chat request received from visitor {visitor_id} (name: {visitor_name or 'unknown'})")
        print(f"[INFO] Message: {message[:100]}..." if len(message) > 100 else f"[INFO] Message: {message}")
        print(f"[INFO] Target user ID: {target_user_id or 'default'}")
        
        # Basic input validation
        if not message or message.strip() == "":
            print("[WARNING] Empty message received")
            return models.ChatResponse(
                response="I didn't receive a message. Could you please try again?",
                query_time_ms=0
            )
        
        # Get context for the AI by searching vector DB, including relevant conversation history
        print(f"[INFO] Querying vector DB for relevant context and conversation history")
        search_results = query_vector_db(
            query=message, 
            user_id=target_user_id,
            visitor_id=visitor_id,
            include_conversation=True
        )
        
        # Get the profile data - use the target_user_id if provided
        # This allows for user-specific chatbots
        print(f"[INFO] Retrieving profile data")
        profile_data = get_profile_data(user_id=target_user_id)
        
        if not profile_data:
            print("[WARNING] No profile data found - using default responses")
        else:
            # Output profile data for debugging
            profile_id = profile_data.get('id', 'None')
            print(f"[INFO] Profile data retrieved: id={profile_id}")
        
        # Get recent conversation history for this visitor (limit to last 5 messages) from database
        print(f"[INFO] Fetching sequential conversation history for visitor {visitor_id}")
        history_limit = 10  # Get the last 10 messages (5 exchanges)
        chat_history = get_chat_history(
            limit=history_limit, 
            visitor_id=visitor_id,
            target_user_id=target_user_id
        )
        
        # Sort the history by timestamp (oldest first)
        if chat_history:
            chat_history = sorted(
                chat_history,
                key=lambda x: x.get("timestamp", ""),
                reverse=False  # Oldest messages first
            )
            print(f"[INFO] Found {len(chat_history)} previous messages in conversation history")
        else:
            print("[INFO] No previous conversation history found")
            chat_history = []
        
        # Generate the AI response
        print(f"[INFO] Generating AI response with conversation context")
        ai_response = generate_ai_response(
            query=message,
            search_results=search_results,
            profile_data=profile_data,
            chat_history=chat_history
        )
        
        # Brief validation of the response
        if not ai_response or ai_response.strip() == "":
            print("[WARNING] Empty response from AI - using fallback")
            ai_response = "I apologize, but I couldn't formulate a proper response. Could we try a different question?"
        
        # Log the message to the database
        print(f"[INFO] Logging chat message to database")
        log_result = log_chat_message(
            message=message, 
            sender="user", 
            response=ai_response, 
            visitor_id=visitor_id, 
            visitor_name=visitor_name,
            target_user_id=target_user_id
        )
        
        # Also store this conversation exchange in the vector database for semantic search
        message_id = log_result[0]["id"] if log_result and len(log_result) > 0 else None
        print(f"[INFO] Adding conversation to vector database for future reference")
        add_conversation_to_vector_db(
            message=message,
            response=ai_response,
            visitor_id=visitor_id,
            message_id=message_id
        )
        
        # Calculate time taken
        end_time = time.time()
        query_time_ms = (end_time - start_time) * 1000
        print(f"[INFO] Request completed in {query_time_ms:.0f}ms")
        
        return models.ChatResponse(
            response=ai_response,
            query_time_ms=query_time_ms
        )
    
    except Exception as e:
        print(f"Error in chat route: {str(e)}")
        # Log the error, but still try to return a reasonable response
        try:
            ai_response = "I'm sorry, I encountered an error processing your request. Please try again."
            # Try to log the chat message even if there was an error
            log_chat_message(
                message=request.message, 
                sender="user", 
                response=ai_response, 
                visitor_id=request.visitor_id, 
                visitor_name=request.visitor_name,
                target_user_id=request.target_user_id  # Access directly
            )
        except Exception as log_error:
            print(f"Error logging chat message: {log_error}")
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat request: {str(e)}"
        )

@router.get("/history", response_model=models.ChatHistoryResponse)
async def get_chat_history_endpoint(
    limit: int = 50, 
    visitor_id: Optional[str] = Query(None, description="Filter chat history by visitor ID"),
    target_user_id: Optional[str] = Query(None, description="Filter chat history by target user ID")
):
    """
    Get chat history, optionally filtered by visitor ID and/or target user ID
    """
    try:
        # Get history with optional filters
        history = get_chat_history(limit=limit, visitor_id=visitor_id, target_user_id=target_user_id)
        
        print(f"Retrieved {len(history)} chat history items")
        
        # Convert the history to the expected format
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
        
        print(f"Returning response with {len(formatted_history)} items")
        return response
    except Exception as e:
        print(f"Error getting chat history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chat history: {str(e)}"
        ) 