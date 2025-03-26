from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from app.database import supabase
from app.routes.auth import get_current_user

router = APIRouter()

@router.get("/")
async def get_chatbots(
    user_id: Optional[str] = Query(None, description="User ID to get chatbots for"),
    current_user = Depends(get_current_user)
):
    """
    Get chatbots for the authenticated user or the specified user_id if provided
    Only admins or the user themselves can access their chatbots
    """
    try:
        # Use current user's ID if no user_id provided
        target_user_id = user_id or current_user.id
        
        # Users can only access their own chatbots
        if target_user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You can only access your own chatbots"
            )
        
        if not supabase:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
            
        # Query chatbots for the user
        response = supabase.table("chatbots").select("*").eq("user_id", target_user_id).execute()
        
        if response.data:
            return {"chatbots": response.data}
        else:
            return {"chatbots": []}
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting chatbots: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chatbots: {str(e)}"
        )

@router.post("/")
async def create_chatbot(
    chatbot: Dict[str, Any],
    current_user = Depends(get_current_user)
):
    """
    Create a new chatbot for the authenticated user
    """
    try:
        if not supabase:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
            
        # Set user_id to current user
        chatbot["user_id"] = current_user.id
        
        # Add default fields if not provided
        if "name" not in chatbot or not chatbot["name"]:
            chatbot["name"] = "My Chatbot"
            
        if "description" not in chatbot:
            chatbot["description"] = ""
            
        if "is_public" not in chatbot:
            chatbot["is_public"] = False
            
        if "configuration" not in chatbot:
            chatbot["configuration"] = {}
        
        # Insert the chatbot
        response = supabase.table("chatbots").insert(chatbot).execute()
        
        if response.data:
            return response.data[0]
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to create chatbot"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating chatbot: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create chatbot: {str(e)}"
        )

@router.get("/{chatbot_id}")
async def get_chatbot(
    chatbot_id: str,
    current_user = Depends(get_current_user)
):
    """
    Get a specific chatbot by ID
    Users can only get their own chatbots or public chatbots
    """
    try:
        if not supabase:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
            
        # Check if the chatbot exists
        response = supabase.table("chatbots").select("*").eq("id", chatbot_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=404,
                detail="Chatbot not found"
            )
            
        chatbot = response.data[0]
        
        # Check if the user has access to this chatbot
        if chatbot["user_id"] != current_user.id and not chatbot["is_public"]:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this chatbot"
            )
            
        return chatbot
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting chatbot: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chatbot: {str(e)}"
        )

@router.put("/{chatbot_id}")
async def update_chatbot(
    chatbot_id: str,
    chatbot: Dict[str, Any],
    current_user = Depends(get_current_user)
):
    """
    Update an existing chatbot
    Users can only update their own chatbots
    """
    try:
        if not supabase:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
            
        # Check if the chatbot exists and belongs to the user
        check_response = supabase.table("chatbots").select("*").eq("id", chatbot_id).eq("user_id", current_user.id).execute()
        
        if not check_response.data or len(check_response.data) == 0:
            raise HTTPException(
                status_code=404,
                detail="Chatbot not found or doesn't belong to you"
            )
            
        # Remove id and user_id from update data if present
        update_data = {k: v for k, v in chatbot.items() if k not in ["id", "user_id"]}
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Update the chatbot
        response = supabase.table("chatbots").update(update_data).eq("id", chatbot_id).execute()
        
        if response.data:
            return response.data[0]
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to update chatbot"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating chatbot: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update chatbot: {str(e)}"
        )

@router.delete("/{chatbot_id}")
async def delete_chatbot(
    chatbot_id: str,
    current_user = Depends(get_current_user)
):
    """
    Delete a chatbot
    Users can only delete their own chatbots
    """
    try:
        if not supabase:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
            
        # Check if the chatbot exists and belongs to the user
        check_response = supabase.table("chatbots").select("*").eq("id", chatbot_id).eq("user_id", current_user.id).execute()
        
        if not check_response.data or len(check_response.data) == 0:
            raise HTTPException(
                status_code=404,
                detail="Chatbot not found or doesn't belong to you"
            )
            
        # Delete the chatbot
        response = supabase.table("chatbots").delete().eq("id", chatbot_id).execute()
        
        return {"success": True, "message": "Chatbot deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting chatbot: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete chatbot: {str(e)}"
        ) 