import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv
import time
import json
import uuid
import traceback
from typing import List, Dict, Optional

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Use the service role key for backend operations
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") 
# Fallback to SUPABASE_KEY if service key is not set (less ideal, but provides backward compatibility)
if not SUPABASE_KEY:
    logger.warning("SUPABASE_SERVICE_KEY not found, falling back to SUPABASE_KEY. Ensure service role key is set for full backend permissions.")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# --- Add Logging Here (Near Supabase Init) ---
logger.info(f"DATABASE INIT: Attempting Supabase connection.")
logger.info(f"DATABASE INIT: SUPABASE_URL loaded: {bool(SUPABASE_URL)}")
logger.info(f"DATABASE INIT: SUPABASE_KEY loaded: {bool(SUPABASE_KEY)}")
if SUPABASE_KEY:
    key_preview = SUPABASE_KEY[:5] + "..." + SUPABASE_KEY[-5:]
    logger.info(f"DATABASE INIT: SUPABASE_KEY preview: {key_preview}")
    if SUPABASE_KEY.startswith("eyJ"):
        logger.info("DATABASE INIT: Key appears to be a service role key (starts with eyJ).")
    else:
        logger.warning("DATABASE INIT: Key does NOT start with eyJ. Might be an anon key?")
else:
    logger.error("DATABASE INIT: SUPABASE_KEY is NOT LOADED from environment!")
# --- End Logging ---

# Default profile data to use if DB is not available
DEFAULT_PROFILE = {
    "name": "John Doe",
    "bio": "I am John, a software engineer with a passion for building AI and web applications. I specialize in full-stack development and have experience across the entire development lifecycle.",
    "skills": "JavaScript, TypeScript, React, Node.js, Python, FastAPI, PostgreSQL, ChromaDB, Supabase, Next.js, TailwindCSS",
    "experience": "5+ years of experience in full-stack development, with a focus on building AI-powered applications and responsive web interfaces.",
    "interests": "AI, machine learning, web development, reading sci-fi, hiking",
    "location": "San Francisco, CA",
}

# Initialize Supabase client or None if connection fails
supabase: Optional[Client] = None

# Try to connect to Supabase
try:
    logger.info(f"Connecting to Supabase at {SUPABASE_URL[:20]}...")
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Successfully connected to Supabase")
except Exception as e:
    logger.error(f"Failed to connect to Supabase: {e}")
    supabase = None

# Load the in-memory profile from the backup file if it exists
try:
    if os.path.exists('profile_backup.json'):
        with open('profile_backup.json', 'r') as f:
            in_memory_profile = json.load(f)
            logger.info(f"Loaded profile from backup file with name: {in_memory_profile.get('name', 'unknown')}")
    else:
        in_memory_profile = DEFAULT_PROFILE.copy()
        logger.info(f"No backup file found, using default profile with name: {in_memory_profile.get('name', 'unknown')}")
        # Save the default profile to the backup file
        with open('profile_backup.json', 'w') as f:
            json.dump(in_memory_profile, f, indent=2)
            logger.info("Created initial profile backup file")
except Exception as e:
    logger.error(f"Error loading profile from backup: {e}")
    in_memory_profile = DEFAULT_PROFILE.copy()
    logger.warning("Using default profile after backup load error")

in_memory_messages = []
in_memory_chatbots = []

def get_profile_data(user_id=None):
    """Get profile data from Supabase or fallback storage"""
    try:
        if not user_id:
            logger.warning("No user_id provided to get_profile_data")
            return DEFAULT_PROFILE
        
        logger.info(f"Getting profile data for user: {user_id}")
        
        # Query Supabase for the profile
        profile_response = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
        
        if profile_response.data and len(profile_response.data) > 0:
            profile_data = profile_response.data[0]
            logger.info(f"Found profile data: {profile_data}")
            
            # Ensure name and location are not null
            if not profile_data.get("name"):
                profile_data["name"] = DEFAULT_PROFILE.get("name", "")
            if not profile_data.get("location"):
                profile_data["location"] = DEFAULT_PROFILE.get("location", "")
            
            return profile_data
        
        # No profile found for this user, create one
        logger.info(f"No profile found for user_id {user_id}, creating new profile")
        
        # Create a new default profile for this user
        new_profile = DEFAULT_PROFILE.copy()
        
        # Ensure name is set - if in_memory_profile has a custom name, use that
        if in_memory_profile.get("name") and in_memory_profile.get("name") != DEFAULT_PROFILE.get("name"):
            new_profile["name"] = in_memory_profile.get("name")
            logger.info(f"Using in-memory profile name: {new_profile['name']}")
        
        # Ensure location is set - if in_memory_profile has a custom location, use that
        if in_memory_profile.get("location") and in_memory_profile.get("location") != DEFAULT_PROFILE.get("location"):
            new_profile["location"] = in_memory_profile.get("location")
            logger.info(f"Using in-memory profile location: {new_profile['location']}")
        
        new_profile.update({
            "user_id": user_id,
            "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        })
        
        try:
            # First check if user exists in users table, if not create it
            user_response = supabase.table("users").select("id").eq("id", user_id).execute()
            if not user_response.data:
                logger.info(f"User {user_id} not found in users table, creating it")
                # Create user in users table
                user_data = {
                    "id": user_id,
                    "username": f"user_{user_id[:8]}",
                    "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }
                supabase.table("users").upsert(user_data).execute()
            
            # Try creating profile
            profile_response = supabase.table("profiles").insert(new_profile).execute()
            
            if profile_response.data and len(profile_response.data) > 0:
                logger.info(f"Created new profile for user_id {user_id}: {profile_response.data[0]['id']}")
                created_profile = profile_response.data[0]
                return created_profile
            
            logger.error(f"Failed to create profile in Supabase: {profile_response}")
            # Fall back to in-memory profile with user_id
            
        except Exception as create_error:
            logger.error(f"Error creating profile: {create_error}")
            logger.error(f"Error trace: {traceback.format_exc()}")
            # Fall back to in-memory profile with user_id
        
        # If we reach here, we need to return a fallback profile with the user_id
        logger.warning(f"Using in-memory profile as fallback for user_id: {user_id}")
        fallback_profile = in_memory_profile.copy()
        fallback_profile["user_id"] = user_id
        return fallback_profile
        
    except Exception as e:
        logger.error(f"Error in get_profile_data: {e}")
        logger.error(f"Error trace: {traceback.format_exc()}")
        return DEFAULT_PROFILE

def save_profile_to_file():
    """Save the in-memory profile to a file for persistence"""
    try:
        with open('profile_backup.json', 'w') as f:
            json.dump(in_memory_profile, f, indent=2)
        logger.info("Saved in-memory profile to file for persistence")
    except Exception as e:
        logger.error(f"Error saving profile to file: {e}")

def update_profile_data(data, user_id=None):
    """
    Update the profile data in Supabase
    If user_id is provided, try to update the profile for that user
    """
    try:
        # Add or update timestamps
        data["updated_at"] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        if not data.get("created_at"):
            data["created_at"] = data["updated_at"]
        
        # Check for user_id in data or use the provided user_id
        effective_user_id = data.get('user_id') or user_id
        
        logger.info(f"Updating profile with data keys: {list(data.keys())}")
        logger.info(f"User ID from parameter: {user_id}, User ID from data: {data.get('user_id')}")
        logger.info(f"Effective user_id for profile update: {effective_user_id}")
        
        # Filter out any fields that might not be in the schema
        # These are the known safe fields in our profiles table
        safe_fields = ["id", "user_id", "bio", "skills", "experience", 
                        "interests", "name", "location", 
                        "created_at", "updated_at",
                        "calendly_link", "meeting_rules", "profile_photo_url"]
        
        logger.debug(f"[DB Log] Safe fields for filtering: {safe_fields}")

        # Keep keys that are in safe_fields. Allow None for profile_photo_url as the column is nullable.
        # This ensures the key passes through if present in the incoming 'data' dict.
        filtered_data = {k: v for k, v in data.items() if k in safe_fields}
        
        logger.info(f"Filtered profile data to: {list(filtered_data.keys())}")
        logger.debug(f"[DB Log] Filtered data (full dictionary): {filtered_data}")
        
        # Handle required fields
        required_fields = ["bio", "skills", "experience", "interests"]
        for field in required_fields:
            if field not in filtered_data or filtered_data[field] is None or filtered_data[field] == "":
                filtered_data[field] = DEFAULT_PROFILE.get(field, "Not specified")
                logger.info(f"Using default value for required field: {field}")
        
        # Ensure name and location are never empty strings or None
        if not filtered_data.get("name") or filtered_data["name"].strip() == "":
            filtered_data["name"] = DEFAULT_PROFILE.get("name", "Anonymous User")
            logger.info(f"Using default name: {filtered_data['name']}")
                
        if not filtered_data.get("location") or filtered_data["location"].strip() == "":
            filtered_data["location"] = DEFAULT_PROFILE.get("location", "Unknown Location")
            logger.info(f"Using default location: {filtered_data['location']}")
        
        if supabase:
            logger.info(f"Attempting to update profile in Supabase")
            
            if effective_user_id:
                # First check if this user exists in the users table by trying to get their auth data
                logger.info(f"Checking if user exists in Supabase auth/users")
                try:
                    # If the user was created through Supabase Auth, they should exist in auth.users
                    # So we'll directly try to create the user in our users table without checking first
                    user_data = {
                        "id": effective_user_id,
                        "username": filtered_data.get("name") or f"user_{effective_user_id[:8]}",
                        "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                        "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                    }
                    # Use upsert instead of insert to handle both new and existing users
                    user_response = supabase.table("users").upsert(user_data).execute()
                    logger.info(f"Upserted user in users table: {user_response.data}")
                except Exception as user_error:
                    logger.error(f"Error upserting user in users table: {user_error}")
                    # If this fails, it could be permissions or it could be that the auth.users record doesn't exist
                    # We'll continue anyway and try to create/update the profile
                
                # Now check if user already has a profile
                logger.info(f"Checking for existing profile with user_id: {effective_user_id}")
                response = supabase.table("profiles").select("id").eq("user_id", effective_user_id).execute()
                logger.info(f"Found profiles matching user_id: {response.data}")
                existing_profile = None if not response.data else response.data[0]
                
                if existing_profile:
                    # Update existing profile
                    profile_id = existing_profile["id"]
                    filtered_data["id"] = profile_id
                    filtered_data["user_id"] = effective_user_id
                    
                    logger.info(f"Updating existing profile with ID: {profile_id} for user: {effective_user_id}")
                    logger.info(f"Update payload: {filtered_data}")
                    try:
                        response = supabase.table("profiles").update(filtered_data).eq("id", profile_id).execute()
                        logger.info(f"Update response: {response.data}")
                        if response.data:
                            logger.info("Successfully updated profile in Supabase")
                            # No need to fall back to in-memory profile
                            result = response.data[0]
                            return result
                        else:
                            logger.error(f"Failed to update profile in Supabase: {response}")
                            # Continue to in-memory fallback
                    except Exception as update_error:
                        logger.error(f"Error during profile update: {update_error}")
                        logger.error(f"Error trace: {traceback.format_exc()}")
                        # Continue to in-memory fallback
                        return None # Return None on failure
                else:
                    # Create new profile for the user
                    logger.info(f"Creating new profile for user: {effective_user_id}")
                    filtered_data["user_id"] = effective_user_id
                    logger.info(f"Insert payload: {filtered_data}")
                    try:
                        response = supabase.table("profiles").insert(filtered_data).execute()
                        logger.info(f"Insert response: {response.data}")
                        if response.data:
                            logger.info("Successfully created profile in Supabase")
                            # No need to fall back to in-memory profile
                            save_profile_to_file()  # Still save for backup
                            result = response.data[0]
                            return result
                        else:
                            logger.error(f"Failed to create profile in Supabase: {response}")
                            # Continue to in-memory fallback
                    except Exception as insert_error:
                        logger.error(f"Error during profile creation: {insert_error} for payload {filtered_data}")
                        logger.error(f"Error trace: {traceback.format_exc()}")
                        # Continue to in-memory fallback
                        return None # Return None on failure
            
            if not effective_user_id:
                logger.warning("No user_id provided, profile will not be created in database")
                return None # Cannot proceed without user_id if Supabase is enabled
        
        # If Supabase is not configured or previous attempts failed and returned None
        logger.error("Failed to update profile in Supabase and Supabase is required.")
        return None 
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        logger.error(f"Error trace: {traceback.format_exc()}")
        return None

def get_user_chatbots(user_id: str) -> List[Dict]:
    """Get all chatbots associated with a specific user ID."""
    if not supabase or not user_id:
        logger.warning(f"Cannot get chatbots - Supabase not connected or no user_id: {user_id}")
        return []
    try:
        logger.info(f"Fetching chatbots for user_id: {user_id}")
        response = supabase.table("chatbots").select("*").eq("user_id", user_id).execute()

        if response.data:
            logger.info(f"Found {len(response.data)} chatbots for user {user_id}")
            # Ensure configuration is a dict, default to empty if null/invalid
            for bot in response.data:
                if not isinstance(bot.get('configuration'), dict):
                    bot['configuration'] = {}
            return response.data
        else:
            logger.info(f"No chatbots found for user {user_id}")
            return []

    except Exception as e:
        logger.error(f"Error fetching chatbots for user {user_id}: {e}")
        logger.error(traceback.format_exc())
        return []

def update_chatbot_config(chatbot_id: str, configuration: Dict, user_id: str) -> Optional[Dict]:
    """Update the configuration for a specific chatbot ID, ensuring the user owns it."""
    if not supabase:
        logger.error("Cannot update chatbot config - Supabase not connected.")
        return None

    try:
        logger.info(f"Updating configuration for chatbot_id: {chatbot_id} by user_id: {user_id}")
        # Update the specific chatbot owned by the user
        response = supabase.table("chatbots") \
            .update({
                "configuration": configuration,
                "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }) \
            .eq("id", chatbot_id) \
            .eq("user_id", user_id) \
            .execute()

        if response.data:
            logger.info(f"Successfully updated config for chatbot {chatbot_id}: {response.data[0]}")
            updated_bot = response.data[0]
            # Ensure configuration is dict
            if not isinstance(updated_bot.get('configuration'), dict):
                 updated_bot['configuration'] = {}
            return updated_bot
        elif len(response.data) == 0:
             logger.warning(f"No chatbot found with id {chatbot_id} owned by user {user_id} to update.")
             return None # Or raise 404?
        else:
            logger.error(f"Error updating chatbot config for {chatbot_id}: {response}")
            return None

    except Exception as e:
        logger.error(f"Exception updating chatbot config for {chatbot_id}: {e}")
        logger.error(traceback.format_exc())
        return None

def get_or_create_chatbot(user_id=None, chatbot_id=None, slug=None):
    """
    Get an existing chatbot or create a default one
    """
    try:
        if not supabase:
            return None

        if chatbot_id:
            # Get specific chatbot by ID
            response = supabase.table("chatbots").select("*").eq("id", chatbot_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
        
        if slug:
            # Get chatbot by slug
            response = supabase.table("chatbots").select("*").eq("public_url_slug", slug).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
        
        if user_id:
            # Get user's default chatbot or create one
            response = supabase.table("chatbots").select("*").eq("user_id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                # User already has a chatbot
                return response.data[0]
            else:
                # Create a default chatbot for the user
                chatbot_data = {
                    "user_id": user_id,
                    "name": "My AI Assistant",
                    "description": "Personal AI chatbot",
                    "is_public": True,
                    "public_url_slug": f"user-{user_id[:8]}",
                    "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }
                
                response = supabase.table("chatbots").insert(chatbot_data).execute()
                if response.data and len(response.data) > 0:
                    return response.data[0]
        
        # Return default chatbot if none found and no user_id provided
        response = supabase.table("chatbots").select("*").limit(1).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
            
        return None
    except Exception as e:
        logger.error(f"Error getting or creating chatbot: {e}")
        return None

def get_or_create_visitor(visitor_id, visitor_name=None):
    """
    Get or create a visitor in the database
    """
    try:
        if not supabase:
            return None
        
        if not visitor_id:
            return None
        
        # Check if visitor already exists using visitor_id field (TEXT) from frontend
        response = supabase.table("visitors").select("*").eq("visitor_id", visitor_id).execute()
        
        if response.data and len(response.data) > 0:
            # Update last_seen timestamp and name if provided
            visitor = response.data[0]
            update_data = {"last_seen": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
            
            if visitor_name and not visitor.get("name"):
                update_data["name"] = visitor_name
            
            update_response = supabase.table("visitors").update(update_data).eq("id", visitor["id"]).execute()
            
            if update_response.data and len(update_response.data) > 0:
                return update_response.data[0]
            return visitor
        
        # Create new visitor with TEXT visitor_id 
        visitor_data = {
            "visitor_id": visitor_id,  # This is the frontend-generated text ID
            "name": visitor_name or "",  # Use empty string if name is not provided
            "first_seen": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "last_seen": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        response = supabase.table("visitors").insert(visitor_data).execute()
        
        if response.data and len(response.data) > 0:
            logger.info(f"Successfully created new visitor with DB ID: {response.data[0]['id']}")
            return response.data[0]
        
        return None
    except Exception as e:
        logger.error(f"Error getting or creating visitor: {e}")
        logger.error(f"Error trace: {traceback.format_exc()}")
        return None

def get_or_create_conversation(chatbot_id: str, visitor_id: str) -> str:
    """Finds an existing conversation or creates a new one for a given chatbot and visitor."""
    if not supabase:
        logger.error("Supabase client not initialized. Cannot manage conversations.")
        raise ConnectionError("Database connection not available")
    
    if not chatbot_id or not visitor_id:
        logger.error(f"Chatbot ID ({chatbot_id}) and Visitor ID ({visitor_id}) are required to get/create conversation.")
        raise ValueError("Chatbot ID and Visitor ID cannot be null")

    try:
        # Convert IDs to UUIDs for query if they are strings
        try:
            chatbot_uuid = uuid.UUID(chatbot_id)
            visitor_uuid = uuid.UUID(visitor_id)
        except ValueError as e:
            logger.error(f"Invalid UUID format for chatbot_id or visitor_id: {e}")
            raise ValueError(f"Invalid UUID format: {e}")

        logger.info(f"Looking for conversation with chatbot_id={chatbot_uuid} and visitor_id={visitor_uuid}")
        
        # 1. Look for existing conversation
        conv_response = supabase.table("conversations") \
            .select("id") \
            .eq("chatbot_id", str(chatbot_uuid)) \
            .eq("visitor_id", str(visitor_uuid)) \
            .limit(1) \
            .execute()

        if conv_response.data:
            conversation_id = conv_response.data[0]["id"]
            logger.info(f"Found existing conversation: {conversation_id}")
            return str(conversation_id)
        else:
            logger.info("No existing conversation found. Creating a new one.")
            
            # 2. Get chatbot owner's user_id
            chatbot_response = supabase.table("chatbots") \
                .select("user_id") \
                .eq("id", str(chatbot_uuid)) \
                .limit(1) \
                .execute()

            if not chatbot_response.data:
                logger.error(f"Chatbot with ID {chatbot_uuid} not found.")
                raise ValueError(f"Chatbot not found: {chatbot_uuid}")
            
            chatbot_owner_user_id = chatbot_response.data[0]["user_id"]
            logger.info(f"Found chatbot owner user_id: {chatbot_owner_user_id}")

            # 3. Create new conversation
            new_conv_data = {
                "chatbot_id": str(chatbot_uuid),
                "visitor_id": str(visitor_uuid),
                "user_id": str(chatbot_owner_user_id) 
                # created_at, updated_at, last_message_at will use defaults or trigger
            }
            
            insert_response = supabase.table("conversations") \
                .insert(new_conv_data) \
                .execute()

            if insert_response.data:
                new_conversation_id = insert_response.data[0]["id"]
                logger.info(f"Successfully created new conversation: {new_conversation_id}")
                return str(new_conversation_id)
            else:
                logger.error(f"Failed to insert new conversation: {insert_response.error}")
                # Attempt to refetch in case of race condition
                time.sleep(0.5) 
                refetch_response = supabase.table("conversations") \
                    .select("id") \
                    .eq("chatbot_id", str(chatbot_uuid)) \
                    .eq("visitor_id", str(visitor_uuid)) \
                    .limit(1) \
                    .execute()
                if refetch_response.data:
                   return str(refetch_response.data[0]["id"])
                else:
                   raise Exception(f"Failed to create or retrieve conversation after insert attempt: {insert_response.error}")

    except Exception as e:
        logger.error(f"Error getting or creating conversation: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise e

def log_chat_message(conversation_id: str, message: str, sender="user", response: Optional[str] = None, metadata: Optional[Dict] = None):
    """Logs a message and its response to the database, linked to a conversation."""
    try:
        if not supabase:
            logger.error("Supabase client not initialized. Cannot log chat messages.")
            # Optional: Fallback to in-memory logging if needed
            # in_memory_messages.append({"message": message, "response": response, "timestamp": time.time(), "sender": sender, "conversation_id": conversation_id})
            return None
        
        if not conversation_id:
            raise ValueError("conversation_id is required to log a message.")

        try:
            # Validate conversation_id is a UUID
            conversation_uuid = uuid.UUID(conversation_id)
            logger.info(f"Valid conversation UUID: {conversation_uuid}")
        except ValueError:
            logger.error(f"Invalid UUID format for conversation_id: {conversation_id}")
            raise ValueError("Invalid conversation_id format.")

        # --- Get chatbot_id from conversation ---
        try:
            # Query conversations table to get chatbot_id based on conversation_id
            conv_data_response = (supabase.table("conversations")
                .select("chatbot_id")
                .eq("id", str(conversation_uuid))
                .limit(1)
                .execute())

            if not conv_data_response.data:
                logger.error(f"Could not find conversation with ID: {conversation_uuid} to get chatbot_id.")
                raise ValueError(f"Conversation not found: {conversation_uuid}")

            chatbot_id = conv_data_response.data[0].get("chatbot_id")
            if not chatbot_id:
                 logger.error(f"Chatbot ID not found in conversation record: {conversation_uuid}")
                 raise ValueError("Chatbot ID missing from conversation record")

            logger.info(f"Found chatbot_id {chatbot_id} for conversation {conversation_uuid}")

        except Exception as conv_lookup_err:
             logger.error(f"Error looking up chatbot_id for conversation {conversation_uuid}: {conv_lookup_err}")
             raise conv_lookup_err
        # --- End Get chatbot_id ---

        message_data = {
            "conversation_id": str(conversation_uuid),
            "chatbot_id": str(chatbot_id),
            "message": message,
            "response": response,
            "sender": sender,
            "metadata": metadata or {},
            "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) # Keep timestamp for potential compatibility? Check schema.sql
            # Removed direct chatbot_id, visitor_id - these are in the conversation table
        }
        
        logger.info(f"Logging message for conversation_id: {conversation_id}")
        logger.info(f"Message data: {json.dumps(message_data, default=str)}")
        
        insert_response = supabase.table("messages").insert(message_data).execute()

        # Check the response to verify insertion
        if insert_response and insert_response.data and len(insert_response.data) > 0:
            logger.info(f"Message saved successfully with ID: {insert_response.data[0].get('id', 'unknown')}")
            logger.info(f"Saved with conversation_id: {insert_response.data[0].get('conversation_id', 'missing')}")
            return insert_response.data # Return the inserted data
        else:
            logger.warning(f"Message insertion response didn't include expected data: {insert_response}")
            return None # Return None on failure or no data

    except Exception as e:
        logger.error(f"Error logging chat message: {e}")
        logger.error(traceback.format_exc())
        return None # Return None on exception

def get_chat_history(conversation_id: str, limit: int = 50):
    """Gets chat history for a specific conversation from Supabase."""
    try:
        if not supabase:
            logger.error("Supabase client not initialized. Cannot get chat history.")
            # Optional: Fallback to in-memory filtering if needed
            # relevant_messages = [m for m in in_memory_messages if m.get('conversation_id') == conversation_id]
            # return relevant_messages[-limit:]
            return []
        
        if not conversation_id:
             logger.error("No conversation_id provided to get_chat_history")
             raise ValueError("conversation_id is required to fetch chat history.")
        
        try:
            # Validate conversation_id is a UUID
            conversation_uuid = uuid.UUID(conversation_id)
            logger.info(f"Valid conversation UUID: {conversation_uuid}")
        except ValueError:
            logger.error(f"Invalid UUID format for conversation_id: {conversation_id}")
            raise ValueError("Invalid conversation_id format.")

        logger.info(f"Fetching chat history for conversation_id: {conversation_id}, limit: {limit}")
        
        try:
            query = supabase.table("messages") \
                .select("*") \
                .eq("conversation_id", str(conversation_uuid)) \
                .order("created_at", desc=False) \
                .limit(limit)
            
            logger.debug(f"Executing query: {query}")
            response = query.execute()
            
            if response and hasattr(response, 'data'):
                logger.info(f"Retrieved {len(response.data)} messages for conversation {conversation_id}")
                return response.data
            else:
                logger.warning(f"Query response does not contain data attribute: {response}")
                return []
        except Exception as query_error:
            logger.error(f"Error executing query: {query_error}")
            return []
            
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return [] # Return empty list on error

def verify_admin_login(username, password):
    """
    Verify admin login credentials against the database
    """
    try:
        if supabase:
            response = supabase.table("admin_users").select("*").eq("username", username).limit(1).execute()
            
            if response.data and len(response.data) > 0:
                user = response.data[0]
                # In a real application, use a proper password hashing library
                if user["password_hash"] == password:
                    logger.info(f"Admin login successful for user: {username}")
                    return True
            
            logger.info(f"Admin login failed for user: {username}")
            return False
        else:
            logger.warning("Supabase client not available, using default admin check")
            # Fallback for demo purposes - in production, always use the database
            return username == "admin" and password == "admin123"
    except Exception as e:
        logger.error(f"Error verifying admin login: {e}")
        # Fallback for demo purposes
        return username == "admin" and password == "admin123"

def is_admin_user(user_id=None, email=None):
    """
    Check if a user is an admin based on user_id or email
    """
    try:
        if not supabase:
            logger.warning("Supabase client not available, admin check failed")
            return False
            
        if not user_id and not email:
            logger.warning("No user_id or email provided for admin check")
            return False
            
        query = supabase.table("admin_users").select("*")
        
        # Build query conditions
        conditions = []
        if user_id:
            conditions.append(f"user_id.eq.{user_id}")
        if email:
            conditions.append(f"email.eq.{email}")
            
        if conditions:
            query = query.or_(",".join(conditions))
            
        response = query.limit(1).execute()
        
        if response.data and len(response.data) > 0:
            logger.info(f"Found admin user: {response.data[0]}")
            return True
            
        logger.info(f"No admin user found for user_id={user_id}, email={email}")
        return False
    except Exception as e:
        logger.error(f"Error checking admin user status: {e}")
        return False

def check_schema_applied():
    """Check if the schema has been properly applied to Supabase"""
    if not supabase:
        logger.warning("Cannot check schema - Supabase client not initialized")
        return False
    
    try:
        # Check if profiles table has the expected columns
        logger.info("Checking if schema has been properly applied...")
        
        # Check if profiles table exists and has essential columns (e.g., bio)
        try:
            response = supabase.table("profiles").select("id, bio").limit(1).execute()
            logger.info(f"Profiles table exists, sample response: {response.data}")
            has_essential_cols = True
        except Exception as e:
            logger.warning(f"Failed to query profiles table or essential columns don't exist: {e}")
            has_essential_cols = False
            
        if has_essential_cols:
            logger.info("Schema verification passed: profiles table seems okay")
            return True
        else:
            logger.warning("Schema verification failed: profiles table missing essential columns")
            logger.warning("Please apply the schema by running the SQL in apply_schema.sql")
            return False
    except Exception as e:
        logger.error(f"Error checking schema: {e}")
        logger.error(f"Error trace: {traceback.format_exc()}")
        return False

# Call this function on startup to check schema status
schema_ok = check_schema_applied()

def get_all_profiles():
    """
    Get all user profiles from the database
    """
    try:
        if not supabase:
            print("Supabase client not initialized")
            return []
        
        response = supabase.table("profiles").select("*").execute()
        profiles = response.data
        
        return profiles
    except Exception as e:
        print(f"Error getting all profiles: {e}")
        return []

def get_all_documents():
    """
    Get all documents from the database
    """
    try:
        if not supabase:
            print("Supabase client not initialized")
            return []
        
        response = supabase.table("user_documents").select("*").execute()
        
        # If no documents found, try to create the test document
        if not response.data:
            logger.info("No documents found, adding test document")
            create_test_document()
            # Try fetching again
            response = supabase.table("user_documents").select("*").execute()
            
        return response.data
    except Exception as e:
        print(f"Error getting all documents: {e}")
        return []

def create_test_document():
    """
    Create a test document for the system - specifically the truck driver persona
    """
    try:
        if not supabase:
            logger.error("Supabase client not initialized")
            return False
            
        # Check if document already exists
        user_id = "9837e518-80f6-46d4-9aec-cf60c0d8be37"  # Ciril's user ID
        
        existing = supabase.table("user_documents").select("*").eq("user_id", user_id).eq("title", "Truck_Driver_Persona").execute()
        
        if existing.data and len(existing.data) > 0:
            logger.info(f"Test document already exists with ID: {existing.data[0]['id']}")
            return True
            
        # Create the document
        test_doc = {
            "user_id": user_id,
            "title": "Truck_Driver_Persona",
            "file_name": "Truck_Driver_Persona.pdf",
            "file_size": "2070",
            "mime_type": "application/pdf",
            "storage_path": f"{user_id}/1743267312011_Truck_Driver_Persona.pdf",
            "extracted_text": """
--- Page 1 ---
Name: Jack Thompson
Age: 45
Gender: Male
Experience: 20 years
Workplace: Thompson Freight Services
Location: Texas, USA
Bio & Background:
A highly skilled and reliable truck driver with two decades of experience in long-haul transportation.
Dedicated to
timely and safe deliveries while ensuring compliance with traffic and safety regulations.
Key Skills:
- Long-distance driving
- Vehicle maintenance & troubleshooting
- Route planning & navigation
- Time management
- Safety compliance
Daily Routine:
6:00 AM - 8:00 AM: Pre-trip inspection & loading
8:00 AM - 12:00 PM: Driving & deliveries
12:00 PM - 1:00 PM: Break & rest
1:00 PM - 6:00 PM: More driving & fuel stops
6:00 PM - 8:00 PM: End-of-day checks & rest
Challenges & Pain Points:
- Long hours away from family
- Fatigue from extended driving
- Unpredictable weather & road conditions
Motivations:
--- Page 2 ---
- Financial stability for family
- Passion for the open road
- Pride in timely deliveries & service
Quote:
"Being a truck driver is not just a job; it's a lifestyle of commitment and resilience."
"""
        }
        
        # Insert into user_documents
        result = supabase.table("user_documents").insert(test_doc).execute()
        
        if result.data:
            logger.info(f"Successfully created test document with ID: {result.data[0]['id']}")
            return True
        else:
            logger.error(f"Failed to create test document: {result.error}")
            return False
            
    except Exception as e:
        logger.error(f"Error creating test document: {e}")
        return False

def get_visitor_id_from_session(session_id: str) -> Optional[str]:
    """Get visitor ID associated with a session ID"""
    try:
        if not supabase:
            logger.error("Supabase client not initialized. Cannot get visitor ID from session.")
            return None
        
        if not session_id:
            logger.error("No session_id provided to get_visitor_id_from_session")
            return None
        
        # Query Supabase for the visitor ID
        response = supabase.table("visitors").select("visitor_id").eq("session_id", session_id).execute()
        
        if response.data and len(response.data) > 0:
            visitor_id = response.data[0]["visitor_id"]
            logger.info(f"Found visitor ID: {visitor_id} for session: {session_id}")
            return visitor_id
        else:
            logger.info(f"No visitor ID found for session: {session_id}")
            return None
    except Exception as e:
        logger.error(f"Error getting visitor ID from session: {e}")
        logger.error(traceback.format_exc())
        return None 

# --- Notes Functions ---

def get_notes(user_id: uuid.UUID) -> List[Dict]:
    """Get all notes for a specific user using a privileged SQL function via RPC."""
    if not supabase:
        logger.error("Supabase client not initialized. Cannot fetch notes.")
        return []
    if not user_id:
        logger.error("User ID is required to fetch notes.")
        return []

    try:
        # Prepare parameters for the RPC call
        params = {'p_user_id': str(user_id)}
        logger.info(f"RPC CALL: Attempting to call get_notes_privileged with user_id: {user_id}")

        # --- RPC Call ---
        try:
            response = supabase.rpc('get_notes_privileged', params).execute()
            logger.info(f"RPC CALL RESPONSE (get_notes): {response}") # Log the full response

            if hasattr(response, 'data') and isinstance(response.data, list):
                logger.info(f"RPC CALL SUCCESS (get_notes): Found {len(response.data)} notes for user {user_id}")
                return response.data # Return the list of notes
            else:
                error_details = getattr(response, 'error', None)
                status_code = getattr(response, 'status_code', 'N/A')
                logger.error(f"RPC CALL FAILED (get_notes): Invalid data format or error. Status: {status_code}, Error: {error_details}")
                return [] # Return empty list on failure/invalid format

        except Exception as rpc_error:
            logger.error(f"RPC CALL EXCEPTION (get_notes): An error occurred during RPC call.")
            error_details = {
                 "message": getattr(rpc_error, 'message', str(rpc_error)),
                 "code": getattr(rpc_error, 'code', 'N/A'),
                 "details": getattr(rpc_error, 'details', None)
            }
            logger.error(f"Supabase RPC Error Details: {error_details}")
            logger.error(f"Full Traceback: {traceback.format_exc()}")
            return [] # Return empty list on exception

    except Exception as e:
        logger.error(f"PRE-RPC EXCEPTION (get_notes): Error preparing for RPC call for user {user_id}: {e}")
        logger.error(f"Full Traceback: {traceback.format_exc()}")
        return []

def create_note(user_id: uuid.UUID, content: str) -> Optional[Dict]:
    """Create a new note using a privileged SQL function via RPC."""
    if not supabase:
        logger.error("ACTION FAILED: Supabase client not initialized. Cannot create note.")
        return None
    if not user_id:
        logger.error("ACTION FAILED: User ID is required to create a note.")
        return None
    if not content:
        logger.error("ACTION FAILED: Note content cannot be empty.")
        return None

    try:
        # Prepare parameters for the RPC call
        params = {
            'p_user_id': str(user_id),
            'p_content': content
        }
        logger.info(f"RPC CALL: Attempting to call create_note_privileged with params: {params}")

        # --- RPC Call ---
        try:
            # Execute the PostgreSQL function
            response = supabase.rpc('create_note_privileged', params).execute()
            logger.info(f"RPC CALL RESPONSE (create_note): {response}") # Log the full response

            # Check response structure
            if hasattr(response, 'data') and response.data and len(response.data) > 0:
                created_note_data = response.data[0]
                # Basic check for expected fields based on function return type
                if created_note_data.get('id') and created_note_data.get('user_id'):
                    logger.info(f"RPC CALL SUCCESS (create_note): Created note with id: {created_note_data.get('id')}")
                    return created_note_data
                else:
                    logger.error(f"RPC CALL FAILED (create_note): Response data missing expected fields. Data: {created_note_data}")
                    return None
            else:
                error_details = getattr(response, 'error', None)
                status_code = getattr(response, 'status_code', 'N/A')
                logger.error(f"RPC CALL FAILED (create_note): No data in response. Status: {status_code}, Error: {error_details}")
                return None

        except Exception as rpc_error:
            logger.error(f"RPC CALL EXCEPTION (create_note): An error occurred during RPC call.")
            error_details = {
                 "message": getattr(rpc_error, 'message', str(rpc_error)),
                 "code": getattr(rpc_error, 'code', 'N/A'),
                 "details": getattr(rpc_error, 'details', None)
            }
            logger.error(f"Supabase RPC Error Details: {error_details}")
            logger.error(f"Full Traceback: {traceback.format_exc()}")
            raise rpc_error # Re-raise for the router to handle

    except Exception as e:
        # Catch errors during parameter preparation or other logic
        logger.error(f"PRE-RPC EXCEPTION (create_note): Error preparing for RPC call for user {user_id}: {e}")
        logger.error(f"Full Traceback: {traceback.format_exc()}")
        return None

# --- End Notes Functions --- 