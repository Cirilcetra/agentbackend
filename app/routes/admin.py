from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
import os
from supabase import create_client, Client
from dotenv import load_dotenv

from app import models
from app.database import supabase

router = APIRouter()

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