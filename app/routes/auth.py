from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import jwt
from datetime import datetime
import os
from pydantic import BaseModel

from app.database import supabase

# Security scheme for JWT Bearer tokens
security = HTTPBearer()

# Pydantic model for the user
class User(BaseModel):
    id: str
    email: Optional[str] = None
    aud: Optional[str] = None
    role: Optional[str] = None
    
# Function to verify the JWT token and extract user information
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """
    Dependency to get the current user from the JWT token
    """
    token = credentials.credentials
    try:
        # Use Supabase's JWT verification if available
        if supabase:
            try:
                # Get user information from the JWT token
                auth_response = supabase.auth.get_user(token)
                if auth_response and auth_response.user:
                    user_data = auth_response.user
                    return User(
                        id=user_data.id,
                        email=user_data.email,
                        aud=user_data.aud,
                        role=user_data.role
                    )
            except Exception as supabase_error:
                print(f"Supabase auth error: {supabase_error}")
                # Fall back to manual JWT verification
        
        # Manual JWT verification as fallback
        try:
            # Get JWT secret from environment
            jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
            if not jwt_secret:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials - JWT secret not configured",
                    headers={"WWW-Authenticate": "Bearer"},
                )
                
            # Decode the JWT token
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
            
            # Extract user information
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token - user ID not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )
                
            return User(
                id=user_id,
                email=payload.get("email"),
                aud=payload.get("aud"),
                role=payload.get("role")
            )
            
        except jwt.PyJWTError as jwt_error:
            print(f"JWT decode error: {jwt_error}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    except Exception as e:
        print(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Optional user dependency that doesn't require authentication
async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[User]:
    """
    Dependency to get the current user from the JWT token, or None if no valid token
    """
    if not credentials:
        return None
        
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None 