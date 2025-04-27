"""
Add this to your app/main.py file to enhance debugging for authentication issues
"""

import logging
import os
from fastapi import Request, Response
import time
import traceback

# Configure more detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("backend_debug.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("auth_debugging")

# Add this middleware to your app in main.py
async def debug_request_middleware(request: Request, call_next):
    """Debug middleware to log all requests and responses"""
    start_time = time.time()
    request_id = f"req_{int(start_time * 1000)}"
    
    # Log request details
    logger.debug(f"[{request_id}] Request: {request.method} {request.url}")
    
    # Log headers for debugging auth issues
    logger.debug(f"[{request_id}] Headers: {dict(request.headers)}")
    
    # Try to get visitor_id from query parameters or cookies 
    try:
        query_params = dict(request.query_params)
        if 'visitor_id' in query_params:
            logger.debug(f"[{request_id}] Visitor ID in query: {query_params['visitor_id']}")
    except Exception as e:
        logger.error(f"[{request_id}] Error parsing query params: {e}")
    
    try:
        cookies = dict(request.cookies)
        if cookies:
            logger.debug(f"[{request_id}] Cookies: {cookies}")
    except Exception as e:
        logger.error(f"[{request_id}] Error parsing cookies: {e}")
        
    # Try to get request body for debugging
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            # Make a copy of the request to avoid consuming it
            body_bytes = await request.body()
            # Add the body back to the request
            async def get_body():
                return body_bytes
            request._body = body_bytes
            request.body = get_body
            
            # Log the body content
            try:
                logger.debug(f"[{request_id}] Request body: {body_bytes.decode()}")
            except UnicodeDecodeError:
                logger.debug(f"[{request_id}] Request body: Binary content")
        except Exception as e:
            logger.error(f"[{request_id}] Error reading request body: {e}")
            logger.error(traceback.format_exc())

    # Process the request
    try:
        response = await call_next(request)
        
        # Log response details
        process_time = time.time() - start_time
        status_code = response.status_code
        logger.debug(f"[{request_id}] Response: Status {status_code} ({process_time:.3f}sec)")
        
        # Check for error responses
        if status_code >= 400:
            logger.error(f"[{request_id}] Error response: {status_code}")
            
            # Try to get response body for error details
            try:
                response_body = b""
                async for chunk in response.body_iterator:
                    response_body += chunk
                
                # Recreate response to avoid consuming it
                response = Response(
                    content=response_body,
                    status_code=status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type
                )
                
                logger.error(f"[{request_id}] Response body: {response_body.decode()}")
            except Exception as e:
                logger.error(f"[{request_id}] Error reading response body: {e}")
                
        return response
    except Exception as e:
        logger.error(f"[{request_id}] Unhandled error: {e}")
        logger.error(traceback.format_exc())
        raise

# Add these instructions to your main.py
"""
# Add this to your main.py after creating the app

from .debug_log_fix import debug_request_middleware

# Add the middleware to the app
app.middleware("http")(debug_request_middleware)
"""

# Also add this debug endpoint to your routes
"""
@app.get("/debug/auth")
async def debug_auth(request: Request):
    """Debug endpoint to check authentication status"""
    auth_header = request.headers.get("Authorization")
    
    # Get visitor ID from query or cookie
    visitor_id = request.query_params.get("visitor_id", None)
    
    # Try to parse JWT if present
    jwt_payload = None
    if auth_header and auth_header.startswith("Bearer "):
        try:
            import jwt
            token = auth_header.replace("Bearer ", "")
            # Just decode without verification for debugging
            jwt_payload = jwt.decode(token, options={"verify_signature": False})
        except Exception as e:
            jwt_payload = {"error": str(e)}
    
    return {
        "authenticated": auth_header is not None,
        "auth_header": auth_header,
        "visitor_id": visitor_id,
        "headers": dict(request.headers),
        "jwt_payload": jwt_payload,
        "cookies": dict(request.cookies)
    }
""" 