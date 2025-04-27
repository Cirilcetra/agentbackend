#!/usr/bin/env python3
"""
debug_visitor_messages.py - Debug and test visitor message storage and retrieval
"""

import os
import sys
import time
import uuid
import json
import logging
import traceback
from dotenv import load_dotenv
from supabase import create_client, Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("debug_visitor_messages.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Supabase connection details
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def get_or_create_visitor(supabase: Client, visitor_id: str, visitor_name: str = "Test Visitor"):
    """Get or create a visitor with the given ID"""
    logger.info(f"Getting or creating visitor with ID: {visitor_id}")
    
    try:
        # Check if visitor already exists
        visitor_response = supabase.table("visitors").select("*").eq("visitor_id", visitor_id).execute()
        
        if visitor_response.data and len(visitor_response.data) > 0:
            visitor = visitor_response.data[0]
            logger.info(f"Found existing visitor with database ID: {visitor['id']}")
            return visitor
        
        # Create new visitor
        visitor_data = {
            "visitor_id": visitor_id,
            "name": visitor_name,
            "first_seen": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "last_seen": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        create_response = supabase.table("visitors").insert(visitor_data).execute()
        
        if create_response.data and len(create_response.data) > 0:
            visitor = create_response.data[0]
            logger.info(f"Created new visitor with database ID: {visitor['id']}")
            return visitor
        else:
            logger.error("Failed to create visitor")
            return None
    except Exception as e:
        logger.error(f"Error in get_or_create_visitor: {e}")
        logger.error(traceback.format_exc())
        return None

def get_chatbot(supabase: Client):
    """Get a chatbot to use for testing"""
    logger.info("Getting a chatbot for testing")
    
    try:
        # Get any chatbot
        chatbot_response = supabase.table("chatbots").select("*").limit(1).execute()
        
        if chatbot_response.data and len(chatbot_response.data) > 0:
            chatbot = chatbot_response.data[0]
            logger.info(f"Found chatbot with ID: {chatbot['id']}")
            return chatbot
        else:
            logger.error("No chatbots found in database")
            return None
    except Exception as e:
        logger.error(f"Error getting chatbot: {e}")
        logger.error(traceback.format_exc())
        return None

def log_chat_message(supabase: Client, message: str, visitor: dict, chatbot: dict):
    """Log a chat message to the database"""
    logger.info(f"Logging chat message: {message[:50] + '...' if len(message) > 50 else message}")
    
    try:
        # Prepare message data
        message_data = {
            "message": message,
            "sender": "user",
            "response": f"Test response to: {message}",
            "visitor_id": visitor["id"],  # UUID from visitors table
            "visitor_id_text": visitor["visitor_id"],  # Original string ID
            "chatbot_id": chatbot["id"],
            "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        # Log data being sent
        logger.info(f"Message data: {json.dumps(message_data, default=str)}")
        
        # Insert the message
        message_response = supabase.table("messages").insert(message_data).execute()
        
        if message_response.data and len(message_response.data) > 0:
            message_record = message_response.data[0]
            logger.info(f"Successfully logged message with ID: {message_record['id']}")
            return message_record
        else:
            logger.error("Failed to log message")
            return None
    except Exception as e:
        logger.error(f"Error logging chat message: {e}")
        logger.error(traceback.format_exc())
        return None

def get_chat_history_by_visitor_id(supabase: Client, visitor_id: str, limit: int = 50):
    """Get chat history using the visitor_id (string) lookup"""
    logger.info(f"Getting chat history for visitor ID: {visitor_id}")
    
    try:
        # First try to get the visitor record
        visitor_response = supabase.table("visitors").select("id").eq("visitor_id", visitor_id).execute()
        
        if visitor_response.data and len(visitor_response.data) > 0:
            visitor_uuid = visitor_response.data[0]["id"]
            logger.info(f"Found visitor with UUID: {visitor_uuid}")
            
            # Try to get messages by the UUID
            uuid_response = supabase.table("messages").select("*").eq("visitor_id", visitor_uuid).order("created_at", desc=True).limit(limit).execute()
            
            if uuid_response.data and len(uuid_response.data) > 0:
                logger.info(f"Found {len(uuid_response.data)} messages using visitor UUID")
                return uuid_response.data
        
        # Try to get messages by visitor_id_text
        text_response = supabase.table("messages").select("*").eq("visitor_id_text", visitor_id).order("created_at", desc=True).limit(limit).execute()
        
        if text_response.data and len(text_response.data) > 0:
            logger.info(f"Found {len(text_response.data)} messages using visitor_id_text")
            return text_response.data
        
        logger.warning(f"No messages found for visitor ID: {visitor_id}")
        return []
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        logger.error(traceback.format_exc())
        return []

def test_visitor_message_flow(supabase: Client):
    """Test the full visitor message flow"""
    logger.info("Testing visitor message flow")
    
    try:
        # Generate a unique test visitor ID
        test_visitor_id = f"debug_v_{uuid.uuid4().hex[:8]}"
        logger.info(f"Generated test visitor ID: {test_visitor_id}")
        
        # Get or create visitor
        visitor = get_or_create_visitor(supabase, test_visitor_id, "Debug Visitor")
        if not visitor:
            logger.error("Failed to get or create visitor")
            return False
        
        # Get a chatbot
        chatbot = get_chatbot(supabase)
        if not chatbot:
            logger.error("Failed to get chatbot")
            return False
        
        # Send multiple test messages
        messages = [
            "This is test message 1",
            "This is test message 2",
            "This is test message 3"
        ]
        
        message_records = []
        for i, message in enumerate(messages):
            logger.info(f"Sending test message {i+1}/{len(messages)}")
            
            record = log_chat_message(supabase, message, visitor, chatbot)
            if record:
                message_records.append(record)
                logger.info(f"Message {i+1} recorded successfully")
            else:
                logger.error(f"Failed to record message {i+1}")
        
        logger.info(f"Sent {len(message_records)}/{len(messages)} test messages")
        
        # Short delay to ensure messages are saved
        time.sleep(1)
        
        # Get chat history and verify
        history = get_chat_history_by_visitor_id(supabase, test_visitor_id)
        
        logger.info(f"Retrieved {len(history)} messages from chat history")
        
        # Check if all messages were retrieved
        if len(history) >= len(messages):
            logger.info("✅ Successfully retrieved all test messages!")
            
            # Output the messages for verification
            for i, msg in enumerate(history[:len(messages)]):
                logger.info(f"Message {i+1}: {msg.get('message')}")
            
            return True
        else:
            logger.error(f"❌ Only retrieved {len(history)}/{len(messages)} messages")
            
            # Output the messages that were retrieved
            for i, msg in enumerate(history):
                logger.info(f"Retrieved message {i+1}: {msg.get('message')}")
            
            return False
    except Exception as e:
        logger.error(f"Error in test_visitor_message_flow: {e}")
        logger.error(traceback.format_exc())
        return False

def debug_direct_visitor_query(supabase: Client, visitor_id: str):
    """Debug visitor queries directly to help diagnose issues"""
    logger.info(f"Debugging visitor queries for ID: {visitor_id}")
    
    try:
        # Check if visitor exists in visitors table
        visitor_response = supabase.table("visitors").select("*").eq("visitor_id", visitor_id).execute()
        
        if visitor_response.data and len(visitor_response.data) > 0:
            visitor = visitor_response.data[0]
            logger.info(f"✅ Found visitor in visitors table:")
            logger.info(f"  - Database ID (UUID): {visitor['id']}")
            logger.info(f"  - Visitor ID (TEXT): {visitor['visitor_id']}")
            logger.info(f"  - Name: {visitor.get('name', 'None')}")
            
            # Now check messages with visitor_id (UUID)
            uuid_response = supabase.table("messages").select("*").eq("visitor_id", visitor['id']).execute()
            
            if uuid_response.data and len(uuid_response.data) > 0:
                logger.info(f"✅ Found {len(uuid_response.data)} messages with visitor UUID")
            else:
                logger.warning("⚠️ No messages found with visitor UUID")
                
            # Check messages with visitor_id_text
            text_response = supabase.table("messages").select("*").eq("visitor_id_text", visitor_id).execute()
            
            if text_response.data and len(text_response.data) > 0:
                logger.info(f"✅ Found {len(text_response.data)} messages with visitor_id_text")
            else:
                logger.warning("⚠️ No messages found with visitor_id_text")
                
            return True
        else:
            logger.error(f"❌ Visitor not found in visitors table: {visitor_id}")
            return False
    except Exception as e:
        logger.error(f"Error in debug_direct_visitor_query: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function"""
    logger.info("Starting visitor message debug script")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set in .env file")
        sys.exit(1)
    
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Connected to Supabase")
        
        # Check for specific visitor ID to debug
        if len(sys.argv) > 1:
            visitor_id = sys.argv[1]
            logger.info(f"Debugging specific visitor ID: {visitor_id}")
            
            debug_direct_visitor_query(supabase, visitor_id)
        else:
            # Run the full test flow
            if test_visitor_message_flow(supabase):
                logger.info("✅ Visitor message flow test passed!")
            else:
                logger.error("❌ Visitor message flow test failed")
                sys.exit(1)
    except Exception as e:
        logger.error(f"Error in main: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 