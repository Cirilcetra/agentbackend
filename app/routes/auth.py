from fastapi import APIRouter, Depends, HTTPException, status, Body
from app.database import supabase
from app.auth import get_current_user, User
from pydantic import BaseModel, EmailStr
import logging
import os
import jwt
import base64

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UserResponse(BaseModel):
    id: str
    email: str = None
    authenticated: bool = True

class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    username: str = None  # Optional username, will use email if not provided

@router.get("/me", response_model=UserResponse)
async def get_authenticated_user(current_user: User = Depends(get_current_user)):
    """Get the current authenticated user"""
    logger.info(f"Authenticated user: id={current_user.id}, email={current_user.email}")
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        authenticated=True
    )

@router.get("/me/debug", response_model=UserResponse)
async def get_debug_user():
    """Temporary endpoint to test authentication without JWT verification"""
    logger.info("Debug authentication endpoint called")
    
    # Create a fake user for testing
    user_id = "debug-user-id-123"
    email = "debug@example.com"
    
    logger.info(f"Returning debug user: id={user_id}, email={email}")
    return UserResponse(
        id=user_id,
        email=email,
        authenticated=True
    )

@router.get("/jwt-settings")
async def check_jwt_settings():
    """Check JWT settings for debugging"""
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    
    # Prepare response data, being careful not to expose sensitive information
    response = {
        "secret_configured": bool(jwt_secret),
        "secret_length": len(jwt_secret) if jwt_secret else 0,
        "secret_first_chars": jwt_secret[:3] + "..." if jwt_secret and len(jwt_secret) > 3 else None,
        "secret_last_chars": "..." + jwt_secret[-3:] if jwt_secret and len(jwt_secret) > 3 else None
    }
    
    # Check if the jwt_secret is base64 encoded
    is_base64 = False
    if jwt_secret:
        try:
            decoded = base64.b64decode(jwt_secret)
            is_base64 = True
            response["is_base64"] = True
            response["decoded_length"] = len(decoded)
        except:
            response["is_base64"] = False
    
    # Test JWT creation with this secret
    try:
        test_payload = {"test": "payload"}
        test_token = jwt.encode(test_payload, jwt_secret, algorithm="HS256")
        decoded = jwt.decode(test_token, jwt_secret, algorithms=["HS256"])
        response["test_token_creation"] = "success"
        response["test_token_verification"] = "success"
    except Exception as e:
        response["test_token_creation"] = str(e)
    
    return response

@router.post("/signup")
async def create_user(data: SignUpRequest = Body(...)):
    """
    Create a new user with Supabase Auth and also add to custom users table
    """
    try:
        if not supabase:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Supabase client not initialized"
            )
        
        # Step 1: Create user in Supabase Auth
        logger.info(f"Creating user in Supabase Auth: {data.email}")
        auth_response = supabase.auth.admin.create_user({
            "email": data.email,
            "password": data.password,
            "email_confirm": True  # Automatically confirm email for testing
        })
        
        if auth_response.error:
            logger.error(f"Error creating user in Supabase Auth: {auth_response.error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error creating user: {auth_response.error.message}"
            )
        
        # Extract user ID
        user_id = auth_response.data.user.id
        logger.info(f"User created in Auth with ID: {user_id}")
        
        # Step 2: Insert record into custom users table
        # Generate username from email if not provided
        username = data.username or data.email.split('@')[0]
        
        logger.info(f"Adding user to custom users table with ID: {user_id}, username: {username}")
        users_response = supabase.table("users").insert({
            "id": user_id,
            "username": username
        }).execute()
        
        if users_response.error:
            logger.error(f"Error adding user to custom table: {users_response.error}")
            # Try to clean up auth user if we can't add to users table
            try:
                supabase.auth.admin.delete_user(user_id)
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup of auth user: {cleanup_error}")
                
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating user record: {users_response.error.message}"
            )
        
        return {
            "id": user_id,
            "email": data.email,
            "message": "User created successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )

@router.post("/test-token")
async def test_token_decoding(token: str = Body(..., embed=True)):
    """Test endpoint to decode JWT token and check validity"""
    try:
        logger.info(f"Testing token decoding: {token[:10]}...")
        
        # Check if JWT secret is configured
        if not os.getenv("SUPABASE_JWT_SECRET"):
            return {
                "error": "SUPABASE_JWT_SECRET not configured",
                "status": "failed"
            }
        
        # First try to decode without verification
        try:
            unverified_payload = jwt.decode(
                token, 
                options={"verify_signature": False}
            )
            logger.info(f"Token decoded without verification: {unverified_payload}")
        except Exception as e:
            logger.error(f"Failed to decode token without verification: {str(e)}")
            return {
                "error": f"Invalid token format: {str(e)}",
                "status": "failed"
            }
        
        # Try to decode with verification
        try:
            jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
            verified_payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                options={"verify_signature": True}
            )
            logger.info(f"Token verified successfully: {verified_payload}")
            return {
                "message": "Token is valid",
                "payload": verified_payload,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Failed to verify token: {str(e)}")
            return {
                "error": f"Token verification failed: {str(e)}",
                "jwt_secret_first_10_chars": jwt_secret[:10] if jwt_secret else "None",
                "status": "failed"
            }
            
    except Exception as e:
        logger.error(f"Unexpected error testing token: {str(e)}")
        return {
            "error": f"Unexpected error: {str(e)}",
            "status": "failed"
        } 