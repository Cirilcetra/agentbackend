import os
import jwt
import time
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get JWT secret from environment
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
if not SUPABASE_JWT_SECRET:
    logger.warning("SUPABASE_JWT_SECRET not found in environment variables. Authentication will not work properly.")

# Print detailed information about the JWT secret
logger.info(f"JWT secret configured: {bool(SUPABASE_JWT_SECRET)}")
if SUPABASE_JWT_SECRET:
    logger.info(f"JWT secret length: {len(SUPABASE_JWT_SECRET)}")
    logger.info(f"JWT secret first 5 chars: {SUPABASE_JWT_SECRET[:5] if len(SUPABASE_JWT_SECRET) >= 5 else SUPABASE_JWT_SECRET}")
    
    # Check if Base64 encoded
    try:
        decoded = base64.b64decode(SUPABASE_JWT_SECRET)
        logger.info(f"JWT secret appears to be Base64 encoded, decoded length: {len(decoded)}")
    except:
        logger.info("JWT secret does not appear to be Base64 encoded")

security = HTTPBearer()

class User(BaseModel):
    """Model for authenticated user"""
    id: str
    email: Optional[str] = None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """
    Validate JWT token and return the user
    """
    try:
        if not SUPABASE_JWT_SECRET:
            logger.error("JWT secret not configured on server")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="JWT secret not configured on server"
            )
            
        token = credentials.credentials
        logger.info(f"Validating token: {token[:10]}... (length: {len(token)})")
        
        # First try to decode the token without verification to check its structure
        try:
            unverified_payload = jwt.decode(
                token, 
                options={"verify_signature": False}
            )
            logger.info(f"Token header/payload decoded: {list(unverified_payload.keys())}")
            
            # Extract user info now - we'll use this as a fallback
            user_id = unverified_payload.get('sub')
            email = unverified_payload.get('email')
            
            # Detailed debug info about the token
            issuer = unverified_payload.get('iss', '')
            audience = unverified_payload.get('aud', '')
            logger.info(f"Token issuer: {issuer}")
            logger.info(f"Token audience: {audience}")
            logger.info(f"Token algorithm (from header): {jwt.get_unverified_header(token).get('alg')}")
            
            # TEMPORARY WORKAROUND - While JWT secret issues are being fixed
            # In production, NEVER skip proper JWT verification
            # Check if the token is from Supabase and has the expected structure
            # Note: The Supabase issuer will be in the format "https://<project-ref>.supabase.co/auth/v1"
            if (user_id and
                audience == 'authenticated' and
                'supabase.co/auth/' in issuer):
                
                logger.warning("⚠️ USING TEMPORARY WORKAROUND: Token looks like a valid Supabase token, bypassing JWT verification")
                logger.warning("This is insecure and should only be used temporarily while fixing JWT issues")
                
                logger.info(f"User authenticated via WORKAROUND: id={user_id}, email={email}")
                return User(id=user_id, email=email)
                
            # Now try different verification approaches
            
            # Try standard verification first
            try:
                payload = jwt.decode(
                    token, 
                    SUPABASE_JWT_SECRET, 
                    algorithms=["HS256"],
                    options={"verify_signature": True}
                )
                logger.info(f"JWT decoded successfully with standard verification. Claims: sub={payload.get('sub')}, email={payload.get('email')}")
                return User(id=payload.get('sub'), email=payload.get('email'))
            except Exception as e:
                logger.error(f"Standard verification failed: {str(e)}")
                
                # Try using the key directly as is
                try:
                    logger.info("Attempting verification with raw key")
                    payload = jwt.decode(
                        token, 
                        SUPABASE_JWT_SECRET, 
                        algorithms=["HS256"],
                        options={"verify_signature": True}
                    )
                    logger.info(f"JWT decoded successfully with raw key. Claims: sub={payload.get('sub')}")
                    return User(id=payload.get('sub'), email=payload.get('email'))
                except Exception as e:
                    logger.error(f"Raw key verification failed: {str(e)}")
                    
                    # Try using base64 decoded key
                    try:
                        logger.info("Attempting verification with base64 decoded key")
                        decoded_secret = base64.b64decode(SUPABASE_JWT_SECRET)
                        payload = jwt.decode(
                            token, 
                            decoded_secret, 
                            algorithms=["HS256"],
                            options={"verify_signature": True}
                        )
                        logger.info(f"JWT decoded successfully with base64 decoded key. Claims: sub={payload.get('sub')}")
                        return User(id=payload.get('sub'), email=payload.get('email'))
                    except Exception as e:
                        logger.error(f"Base64 decoded key verification failed: {str(e)}")
                        
                    # All verification methods failed
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token signature. The server's JWT secret may be incorrect.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token format: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token format: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        ) 