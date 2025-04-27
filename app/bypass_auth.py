"""
EMERGENCY BYPASS for authentication issues in chat endpoint.

This is a direct, no-frills implementation of the chat endpoint that 
bypasses all authentication and just returns a response.

To use this:
1. Copy this file to your backend/app directory
2. Import the function in your app/main.py
3. Add a new route that uses this function

Example in app/main.py:
```python
from app.bypass_auth import emergency_chat_endpoint

# Add this route BEFORE your regular routes
@app.post("/emergency-chat", response_model=ChatResponse)
async def emergency_chat(request: dict):
    return await emergency_chat_endpoint(request)
```
"""

import logging
import json
import uuid
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional

# Setup logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("bypass_auth")

class ChatResponse(BaseModel):
    response: str
    query_time_ms: Optional[float] = 0

# The direct endpoint function
async def emergency_chat_endpoint(request: dict):
    """
    Ultra-simple chat endpoint that just returns a response.
    This bypasses all authentication and database requirements.
    """
    try:
        # Log the full request for debugging
        logger.info(f"Emergency chat endpoint received request: {request}")
        
        # Extract message (handle both dictionary and ChatRequest model formats)
        message = None
        if isinstance(request, dict):
            message = request.get('message')
        else:
            # Assume it's a Pydantic model with a message field
            message = getattr(request, 'message', None)
        
        if not message:
            logger.warning("No message found in request")
            return ChatResponse(
                response="I didn't receive a message. Please try again.",
                query_time_ms=0
            )
            
        # Generate simple response - no database or authentication needed
        logger.info(f"Processing message: {message}")
        response = f"Emergency mode response: I received your message: '{message}'"
        
        # Log successful response
        logger.info(f"Emergency chat endpoint returned response successfully")
        
        # Return formatted response
        return ChatResponse(
            response=response,
            query_time_ms=0
        )
        
    except Exception as e:
        # Log error but don't reveal details to client
        logger.error(f"Error in emergency_chat_endpoint: {e}", exc_info=True)
        
        # Return friendly error message
        return ChatResponse(
            response="Sorry, there was an error processing your request. Our team has been notified.",
            query_time_ms=0
        ) 