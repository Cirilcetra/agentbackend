from fastapi import APIRouter, HTTPException, Depends, Header, Query
from typing import Optional, List, Dict
import os
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
import uuid

from app import models
from app.database import supabase, get_chat_history

router = APIRouter()

# Set up logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def verify_admin_token(authorization: Optional[str] = Header(None)):
    """
    Verify that a user's token is valid by checking against Supabase Auth
    This function is used as a dependency for protected routes
    Any authenticated user is allowed - we no longer restrict to admin users
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    try:
        # Extract JWT token from Authorization header
        token = authorization.replace("Bearer ", "")
        
        if not token:
            raise HTTPException(status_code=401, detail="Invalid token format")
            
        if not supabase:
            raise HTTPException(status_code=500, detail="Supabase client is not initialized")
            
        # Verify token with Supabase
        result = supabase.auth.get_user(token)
        user = result.user
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
            
        # No longer checking if user is an admin - any authenticated user is allowed
        
        # Return the user for potential further use
        return user
    except Exception as e:
        print(f"Error verifying token: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@router.get("/me", response_model=models.AdminInfoResponse)
async def get_admin_info(user = Depends(verify_admin_token)):
    """
    Get information about the current authenticated user
    """
    try:
        return models.AdminInfoResponse(
            id=user.id,
            email=user.email,
            success=True
        )
    except Exception as e:
        print(f"Error in get_admin_info: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get user info: {str(e)}"
        )

# This endpoint can be removed as we no longer need the admin_users table
# but keeping it for backward compatibility, with modified behavior
@router.post("/create", response_model=models.AdminCreateResponse)
async def create_admin(admin_data: models.AdminCreateRequest):
    """
    Create a new user account
    Signup code is no longer required
    """
    try:
        if not supabase:
            raise HTTPException(
                status_code=500,
                detail="Supabase client is not initialized"
            )
        
        # Create user in Supabase Auth
        user_data = {
            "email": admin_data.email,
            "password": admin_data.password,
            "email_confirm": True  # Auto-confirm email for simplicity
        }
        
        # Create user with corrected API call format
        auth_response = supabase.auth.admin.create_user(user_data)
        
        if not auth_response or not hasattr(auth_response, 'user') or not auth_response.user:
            raise HTTPException(
                status_code=500,
                detail="Failed to create user in Supabase Auth"
            )
                
        user_id = auth_response.user.id
            
        return models.AdminCreateResponse(
            success=True,
            message="User created successfully",
            user_id=user_id
        )
            
    except Exception as e:
        print(f"Error creating user: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create user: {str(e)}"
        )

@router.get("/chat/history", response_model=models.ChatHistoryResponse)
async def get_admin_chat_history(
    limit: int = Query(1000, description="Maximum number of messages to return"),
    target_user_id: Optional[str] = Query(None, description="Filter by user ID"),
    user = Depends(verify_admin_token)
):
    """
    Get all chat history for authenticated users.
    Fetches conversations, messages, and visitor names.
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="Supabase client not initialized")
        
        user_id = target_user_id or user.id
        logger.info(f"Fetching admin chat history for user: {user_id}, limit: {limit}")

        # Step 1: Get all conversations for this user, including visitor_id
        conversations_response = supabase.table("conversations") \
            .select("id, visitor_id") \
            .eq("user_id", user_id) \
            .execute()
        
        if not conversations_response.data:
            logger.info(f"No conversations found for user {user_id}")
            return models.ChatHistoryResponse(history=[], count=0)

        # Create maps: conversation_id -> visitor_id and collect unique visitor_ids
        conversation_to_visitor_map = {}
        visitor_ids = set()
        for conv in conversations_response.data:
            if conv.get("id") and conv.get("visitor_id"):
                conversation_to_visitor_map[conv["id"]] = conv["visitor_id"]
                visitor_ids.add(conv["visitor_id"])

        if not visitor_ids:
            logger.warning(f"No valid visitor IDs found in conversations for user {user_id}")
            return models.ChatHistoryResponse(history=[], count=0)

        # Step 2: Get visitor names for all unique visitor IDs
        visitor_name_map = {}
        if visitor_ids:
            visitors_response = supabase.table("visitors") \
                .select("id, name") \
                .in_("id", list(visitor_ids)) \
                .execute()
            
            if visitors_response.data:
                visitor_name_map = {vis["id"]: vis.get("name") for vis in visitors_response.data}
                logger.info(f"Fetched names for {len(visitor_name_map)} visitors")
            else:
                 logger.warning(f"Could not fetch names for visitor IDs: {visitor_ids}")

        # Step 3: Collect messages from all conversations, adding visitor details
        all_messages = []
        conversation_ids = list(conversation_to_visitor_map.keys())

        if conversation_ids:
             # Fetch messages for all relevant conversations in one go if possible
             # Assuming get_chat_history fetches by ONE conversation_id at a time.
             # If it could fetch for multiple, this loop would be optimized.
             # For now, iterate and fetch individually.
             for conversation_id in conversation_ids:
                 visitor_id = conversation_to_visitor_map.get(conversation_id)
                 if not visitor_id:
                     continue # Should not happen based on map creation

                 # Get messages for this conversation
                 conversation_messages = get_chat_history(conversation_id=conversation_id, limit=limit) # Limit per conversation for now

                 # Add visitor_id and visitor_name to each message
                 visitor_name = visitor_name_map.get(visitor_id)
                 for msg in conversation_messages:
                     if isinstance(msg, dict):
                         msg["visitor_id"] = visitor_id
                         msg["visitor_name"] = visitor_name # Add visitor name
                         msg["timestamp"] = msg.get("created_at") # Ensure timestamp field matches model expectation
                     else:
                         logger.warning(f"Found non-dict message item: {msg} in conversation {conversation_id}")
                 all_messages.extend(conversation_messages or [])

        # Sort all messages by timestamp (most recent first)
        all_messages.sort(key=lambda x: x.get("created_at", "") if isinstance(x, dict) else "", reverse=True)
        
        # Apply overall limit to the combined list
        if limit and len(all_messages) > limit:
            all_messages = all_messages[:limit]
            
        # Ensure all items are dicts and format for the response model
        formatted_history = []
        for msg in all_messages:
             if isinstance(msg, dict):
                 # Ensure keys match ChatHistoryItem model (adjust if needed)
                 # The model expects 'timestamp', so we added it above from 'created_at'
                 try:
                    formatted_history.append(models.ChatHistoryItem(**msg))
                 except Exception as model_error:
                     logger.error(f"Error creating ChatHistoryItem from message data: {msg}, Error: {model_error}")
                     # Optionally skip this message or add a default representation

        logger.info(f"Returning {len(formatted_history)} messages in admin chat history response")
        
        return models.ChatHistoryResponse(
            history=formatted_history,
            count=len(formatted_history)
        )
    except Exception as e:
        logger.error(f"Error getting admin chat history: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chat history: {str(e)}"
        ) 