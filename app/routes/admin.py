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
    page: int = Query(1, description="Page number for pagination", ge=1),
    page_size: int = Query(20, description="Number of messages per page", ge=1, le=100),
    target_user_id: Optional[str] = Query(None, description="Filter by user ID"),
    user = Depends(verify_admin_token)
):
    """
    Get all chat history for authenticated users.
    Fetches conversations, messages, and visitor names with pagination.
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="Supabase client not initialized")
        
        user_id = target_user_id or user.id
        logger.info(f"Fetching admin chat history for user: {user_id}, page: {page}, page_size: {page_size}")

        # Step 1: Fetch all conversations for this user
        conversations_response = supabase.table("conversations") \
            .select("id, visitor_id") \
            .eq("user_id", user_id) \
            .order("created_at", desc=False) \
            .limit(1000) \
            .execute()
        
        if not conversations_response.data:
            logger.info(f"No conversations found for user {user_id}")
            return models.ChatHistoryResponse(history=[], count=0)

        # Extract conversation IDs and visitor IDs in one pass
        conversation_ids = [conv["id"] for conv in conversations_response.data if conv.get("id")]
        conversation_to_visitor = {
            conv["id"]: conv["visitor_id"] 
            for conv in conversations_response.data 
            if conv.get("id") and conv.get("visitor_id")
        }
        visitor_ids = list(set(filter(None, [conv.get("visitor_id") for conv in conversations_response.data])))

        if not conversation_ids:
             logger.warning(f"No valid conversation IDs found for user {user_id}")
             return models.ChatHistoryResponse(history=[], count=0)
             
        if not visitor_ids:
            logger.warning(f"No valid visitor IDs found in conversations for user {user_id}")
            # Proceed, but visitor names might be missing

        # Step 2: Fetch visitor names in a single query
        visitor_name_map = {}
        if visitor_ids:
            try:
                visitors_response = supabase.table("visitors") \
                    .select("id, name") \
                    .in_("id", visitor_ids) \
                    .execute()
                
                if visitors_response.data:
                    visitor_name_map = {vis["id"]: vis.get("name") for vis in visitors_response.data}
                    logger.info(f"Fetched names for {len(visitor_name_map)} visitors")
                else:
                     logger.warning(f"Could not fetch names for visitor IDs: {visitor_ids}")
            except Exception as e:
                logger.error(f"Error fetching visitor names: {e}")


        # Step 3: Fetch messages for all conversations in a single query with pagination
        offset = (page - 1) * page_size
        
        try:
            messages_response = supabase.table("messages") \
                .select("*") \
                .in_("conversation_id", conversation_ids) \
                .order("created_at", desc=True) \
                .range(offset, offset + page_size - 1) \
                .execute()
            
            if messages_response.data is None:
                 logger.warning(f"Messages query returned None data for conversations {conversation_ids}")
                 raw_messages = []
            else:
                 raw_messages = messages_response.data
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            raw_messages = []
        
        # Step 4: Get total message count for pagination
        total_count = 0
        if conversation_ids:
            try:
                count_response = supabase.table("messages") \
                    .select("id", count="exact") \
                    .in_("conversation_id", conversation_ids) \
                    .execute()
                total_count = count_response.count if hasattr(count_response, "count") and count_response.count is not None else 0
            except Exception as count_error:
                logger.warning(f"Could not get exact message count for user {user_id}: {count_error}. Using length of fetched page.")
                total_count = len(raw_messages) # Fallback, might be inaccurate

        # Step 5: Format messages into ChatHistoryItem including visitor details
        formatted_history = []
        for msg in raw_messages:
            conversation_id = msg.get("conversation_id")
            visitor_id = conversation_to_visitor.get(conversation_id)
            visitor_name = visitor_name_map.get(visitor_id) if visitor_id else None
            
            formatted_history.append(
                models.ChatHistoryItem(
                    id=msg.get("id", str(uuid.uuid4())), # Use message ID or generate one
                    message=msg.get("message", ""),
                    sender=msg.get("sender", "unknown"),
                    response=msg.get("response"),
                    timestamp=msg.get("created_at", ""),
                    visitor_id=visitor_id or "unknown", # Provide visitor_id
                    visitor_name=visitor_name, # Add visitor name
                    conversation_id=conversation_id # Add conversation_id
                )
            )

        logger.info(f"Returning {len(formatted_history)} messages for page {page}, total count: {total_count}")
        return models.ChatHistoryResponse(
            history=formatted_history,
            count=total_count
        )

    except Exception as e:
        logger.exception(f"Error fetching admin chat history: {e}") # Log the full traceback
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chat history: {str(e)}"
        ) 

# Add this helper function near the top or before the delete endpoint
async def verify_conversation_owner(conversation_id: uuid.UUID, user_id: uuid.UUID):
    """Verifies that the given user_id owns the specified conversation_id."""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database client not available")
    try:
        response = supabase.table("conversations") \
            .select("user_id") \
            .eq("id", str(conversation_id)) \
            .maybe_single() \
            .execute()

        if response.data and response.data.get("user_id") == str(user_id):
            return True
        else:
            # Log attempted access or just return False
            logger.warning(f"User {user_id} attempted to access conversation {conversation_id} owned by another user or non-existent conversation.")
            return False
    except Exception as e:
        logger.error(f"Error verifying conversation owner for conv {conversation_id}, user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error verifying conversation ownership")


@router.delete("/chat/conversations/{conversation_id}", status_code=204)
async def delete_admin_conversation(
    conversation_id: str,
    user = Depends(verify_admin_token) # Make sure verify_admin_token is defined/imported
):
    """
    Deletes a specific conversation and all its associated messages.
    Ensures the conversation belongs to the authenticated user.
    """
    logger.info(f"Attempting to delete conversation {conversation_id} for user {user.id}")
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")

    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        logger.error(f"Invalid UUID format for conversation_id: {conversation_id}")
        raise HTTPException(status_code=400, detail="Invalid conversation ID format.")

    # Verify the user owns the conversation
    is_owner = await verify_conversation_owner(conv_uuid, user.id)
    if not is_owner:
        logger.warning(f"User {user.id} does not own conversation {conversation_id} or it doesn't exist.")
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this conversation.")

    try:
        # Step 1: Delete associated messages
        logger.info(f"Deleting messages for conversation {conversation_id}")
        delete_messages_response = supabase.table("messages") \
            .delete() \
            .eq("conversation_id", str(conv_uuid)) \
            .execute()
        # Log the data part of the response (should be empty on success)
        logger.info(f"Messages delete response data: {delete_messages_response.data}")

        # Step 2: Delete the conversation itself
        logger.info(f"Deleting conversation record {conversation_id}")
        delete_conv_response = supabase.table("conversations") \
            .delete() \
            .eq("id", str(conv_uuid)) \
            .eq("user_id", str(user.id)) \
            .execute()

        # Log the data part of the response (should be empty on success)
        logger.info(f"Conversation delete response data: {delete_conv_response.data}")

        # If execute() did not raise an exception, assume success or record already gone.
        # Remove the check based on status_code or data presence for delete operations.
        # if delete_conv_response.status_code not in [200, 204] or (hasattr(delete_conv_response, 'data') and not delete_conv_response.data):
        #      logger.warning(f"Conversation {conversation_id} could not be deleted or was already gone.")
             
        logger.info(f"Successfully deleted conversation {conversation_id} and its messages.")
        # No content is returned on successful deletion (status code 204)

    except Exception as e:
        logger.error(f"Error during deletion of conversation {conversation_id}: {e}")
        # Log the traceback for detailed debugging
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation: {str(e)}") 