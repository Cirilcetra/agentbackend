import os
from supabase import create_client, Client
from dotenv import load_dotenv
import time
import json
import uuid
import logging
import copy
import re

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Default profile data to use if DB is not available
DEFAULT_PROFILE = {
    "bio": "I am a software engineer with a passion for building AI and web applications. I specialize in full-stack development and have experience across the entire development lifecycle.",
    "skills": "JavaScript, TypeScript, React, Node.js, Python, FastAPI, PostgreSQL, ChromaDB, Supabase, Next.js, TailwindCSS",
    "experience": "5+ years of experience in full-stack development, with a focus on building AI-powered applications and responsive web interfaces.",
    "projects": "AI-powered portfolio system, real-time analytics dashboard, natural language processing application",
    "interests": "AI, machine learning, web development, reading sci-fi, hiking",
    "project_list": []
}

# Initialize Supabase client or None if connection fails
supabase = None
try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase connection initialized")
    else:
        print("Warning: Missing Supabase environment variables. Using in-memory storage.")
except Exception as e:
    print(f"Error initializing Supabase client: {e}")
    print("Using in-memory storage instead.")

# In-memory storage as fallback
in_memory_profile = DEFAULT_PROFILE.copy()

# Try to load saved profile if it exists
try:
    if os.path.exists('profile_backup.json'):
        with open('profile_backup.json', 'r') as f:
            saved_profile = json.load(f)
            in_memory_profile.update(saved_profile)
            print("Loaded saved profile from profile_backup.json")
except Exception as e:
    print(f"Error loading saved profile: {e}")

in_memory_messages = []

def get_profile_data(user_id=None):
    """
    Get the profile data from Supabase for a specific user
    If user_id is not provided, return default profile
    """
    try:
        if not user_id:
            print("Warning: No user_id provided, using default profile data")
            # Return the default in-memory profile
            return in_memory_profile.copy()
            
        if supabase:
            # Query for the specific user's profile
            response = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                print(f"Found profile for user: {user_id}")
                profile = response.data[0]
                
                # Fetch user's projects
                projects_response = supabase.table("projects").select("*").eq("user_id", user_id).execute()
                
                if projects_response.data:
                    print(f"Found {len(projects_response.data)} projects for user: {user_id}")
                    profile['project_list'] = projects_response.data
                else:
                    profile['project_list'] = []
                    
                return profile
            else:
                print(f"No profile found for user: {user_id}, using default profile")
                # If no profile found for this user, create a copy of the default with the user_id set
                default_profile = in_memory_profile.copy()
                default_profile['user_id'] = user_id
                return default_profile
        
        # Fallback to in-memory profile if Supabase is not available
        print("Supabase is not available, using in-memory profile")
        default_profile = in_memory_profile.copy()
        if user_id:
            default_profile['user_id'] = user_id
        return default_profile
    except Exception as e:
        print(f"Error fetching profile data: {e}")
        # Return default profile on error
        default_profile = in_memory_profile.copy()
        if user_id:
            default_profile['user_id'] = user_id
        return default_profile

def save_profile_to_file():
    """Save the in-memory profile to a file for persistence"""
    try:
        with open('profile_backup.json', 'w') as f:
            json.dump(in_memory_profile, f, indent=2)
        print("Saved in-memory profile to file for persistence")
    except Exception as e:
        print(f"Error saving profile to file: {e}")

def update_profile_data(data, user_id=None):
    """
    Update the profile data in Supabase for a specific user
    """
    try:
        if not user_id:
            print("Error: user_id is required to update profile data")
            return None
            
        if supabase:
            print(f"Updating profile for user: {user_id}")
            
            # Check if profile exists for this user
            response = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
            
            # Prepare profile data (exclude project_list which is stored separately)
            profile_data = {k: v for k, v in data.items() if k != 'project_list' and k != 'id'}
            profile_data['user_id'] = user_id
            profile_data['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            
            if response.data and len(response.data) > 0:
                # Update existing profile
                existing_profile = response.data[0]
                profile_id = existing_profile['id']
                
                response = supabase.table("profiles").update(profile_data).eq("id", profile_id).execute()
                print(f"Updated profile with ID: {profile_id}")
            else:
                # Create new profile
                response = supabase.table("profiles").insert(profile_data).execute()
                print(f"Created new profile for user: {user_id}")
            
            # Handle project_list if provided
            if 'project_list' in data and data['project_list']:
                for project in data['project_list']:
                    if 'id' in project and project['id']:
                        # Update existing project
                        update_project(project['id'], project, user_id)
                    else:
                        # Add new project
                        add_project(project, user_id)
            
            # Get the updated profile to return
            updated_profile = get_profile_data(user_id)
            return updated_profile
        
        # Fallback to in-memory update if Supabase fails
        print("Supabase is not available, using in-memory storage")
        for key, value in data.items():
            if key != 'id':  # Don't overwrite id
                in_memory_profile[key] = value
                
        # Save updated profile to file for persistence
        save_profile_to_file()
        
        return data
    except Exception as e:
        print(f"Error updating profile: {e}")
        return None

def add_project(project_data, user_id=None):
    """
    Add a new project to the database
    """
    try:
        if not user_id:
            print("Error: user_id is required to add a project")
            return None
            
        # Generate a UUID for the project if not provided
        if not project_data.get('id'):
            project_data['id'] = str(uuid.uuid4())
        
        # Set timestamps
        current_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        project_data['created_at'] = current_time
        project_data['updated_at'] = current_time
        
        # Add user_id to the project data
        project_data['user_id'] = user_id
        
        if supabase:
            # Insert project into projects table
            response = supabase.table("projects").insert(project_data).execute()
            print(f"Added new project with ID: {project_data['id']} for user: {user_id}")
            
            # Return the updated profile data
            return get_profile_data(user_id)
        
        # Fallback to in-memory storage
        print("Supabase is not available, using in-memory storage")
        if 'project_list' not in in_memory_profile:
            in_memory_profile['project_list'] = []
            
        in_memory_profile['project_list'].append(project_data)
        save_profile_to_file()
        
        return in_memory_profile
    except Exception as e:
        print(f"Error adding project: {e}")
        return None

def update_project(project_id, project_data, user_id=None):
    """
    Update an existing project
    """
    try:
        if not user_id:
            print("Error: user_id is required to update a project")
            return None
            
        if supabase:
            # Verify the project belongs to the user
            check_response = supabase.table("projects").select("*").eq("id", project_id).eq("user_id", user_id).execute()
            
            if not check_response.data or len(check_response.data) == 0:
                print(f"Project {project_id} not found or does not belong to user {user_id}")
                return None
                
            # Prepare project data for update
            update_data = {k: v for k, v in project_data.items() if k != 'id'}
            update_data['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            
            # Update the project
            response = supabase.table("projects").update(update_data).eq("id", project_id).execute()
            print(f"Updated project with ID: {project_id}")
            
            # Return the updated profile data
            return get_profile_data(user_id)
        
        # Fallback to in-memory storage
        print("Supabase is not available, using in-memory storage")
        if 'project_list' not in in_memory_profile:
            in_memory_profile['project_list'] = []
            
        for i, project in enumerate(in_memory_profile['project_list']):
            if project.get('id') == project_id:
                # Preserve the ID and created_at timestamp
                project_data['id'] = project_id
                if 'created_at' in project:
                    project_data['created_at'] = project['created_at']
                
                # Update the updated_at timestamp
                project_data['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                
                in_memory_profile['project_list'][i] = project_data
                save_profile_to_file()
                return in_memory_profile
        
        return None
    except Exception as e:
        print(f"Error updating project: {e}")
        return None

def delete_project(project_id, user_id=None):
    """
    Delete a project
    """
    try:
        if not user_id:
            print("Error: user_id is required to delete a project")
            return False
            
        if supabase:
            # Verify the project belongs to the user
            check_response = supabase.table("projects").select("*").eq("id", project_id).eq("user_id", user_id).execute()
            
            if not check_response.data or len(check_response.data) == 0:
                print(f"Project {project_id} not found or does not belong to user {user_id}")
                return False
                
            # Delete the project
            response = supabase.table("projects").delete().eq("id", project_id).execute()
            print(f"Deleted project with ID: {project_id}")
            
            return True
        
        # Fallback to in-memory storage
        print("Supabase is not available, using in-memory storage")
        if 'project_list' not in in_memory_profile:
            return False
            
        for i, project in enumerate(in_memory_profile['project_list']):
            if project.get('id') == project_id:
                del in_memory_profile['project_list'][i]
                save_profile_to_file()
                return True
        
        return False
    except Exception as e:
        print(f"Error deleting project: {e}")
        return False

def log_chat_message(message, sender="user", response=None, visitor_id=None, visitor_name=None, target_user_id=None, chatbot_id=None):
    """
    Log a chat message to the database
    
    Args:
        message (str): The message to log
        sender (str): The sender of the message (user, ai, system)
        response (str): Optional response from the AI
        visitor_id (str): Optional visitor ID
        visitor_name (str): Optional visitor name
        target_user_id (str): Optional target user ID
        chatbot_id (str): Optional chatbot ID
        
    Returns:
        bool: True if the message was logged successfully
    """
    try:
        timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        
        # Use a default visitor ID if none provided
        if not visitor_id:
            visitor_id = f"anonymous-{int(time.time())}"
            
        # Log to in-memory messages if Supabase is not available
        if supabase is None:
            logging.warning("Supabase client not initialized, using in-memory messages")
            
            # Initialize the visitor's message list if it doesn't exist
            if visitor_id not in in_memory_messages:
                in_memory_messages[visitor_id] = []
                
            # Add the message to the in-memory messages
            message_data = {
                "id": str(uuid.uuid4()),
                "message": message,
                "sender": sender,
                "visitor_id": visitor_id,
                "visitor_name": visitor_name,
                "target_user_id": target_user_id,
                "chatbot_id": chatbot_id,
                "timestamp": timestamp
            }
            
            # Add response if available
            if response:
                message_data["response"] = response
                
            in_memory_messages[visitor_id].append(message_data)
            logging.info(f"Added message to in-memory messages for visitor: {visitor_id}")
            
            return True
        
        # First, make sure the user has a chatbot or create a default one if needed
        user_chatbot_id = chatbot_id
        
        if target_user_id and not chatbot_id:
            try:
                # Check if user has a chatbot
                chatbot_response = supabase.table("chatbots").select("*").eq("user_id", target_user_id).limit(1).execute()
                
                # If user has a chatbot, use it
                if chatbot_response.data and len(chatbot_response.data) > 0:
                    user_chatbot_id = chatbot_response.data[0]["id"]
                    logging.info(f"Found existing chatbot {user_chatbot_id} for user {target_user_id}")
                else:
                    # Don't attempt to create a chatbot here - let's use NULL for chatbot_id
                    # This avoids RLS policy issues while still allowing messages to be stored
                    logging.info(f"No chatbot found for user {target_user_id}, using NULL for chatbot_id")
                    user_chatbot_id = None
            except Exception as e:
                logging.error(f"Error checking/creating user chatbot: {e}")
                user_chatbot_id = None
        
        # Now log the message
        message_data = {
            "message": message,
            "sender": sender,
            "visitor_id": visitor_id,
            "chatbot_id": user_chatbot_id
        }
        
        # Add optional fields if available
        if visitor_name:
            message_data["visitor_name"] = visitor_name
            
        if target_user_id:
            message_data["user_id"] = target_user_id
            
        if response:
            message_data["response"] = response
            
        # Insert into Supabase
        try:
            result = supabase.table("messages").insert(message_data).execute()
            if hasattr(result, 'data') and len(result.data) > 0:
                logging.info(f"Successfully logged chat message to Supabase: {result.data[0].get('id', 'unknown')}")
                return True
            else:
                logging.warning(f"Unexpected result format when logging message: {result}")
                return False
        except Exception as insert_error:
            logging.error(f"Error logging chat message: {insert_error}")
            
            # Try with just the basic fields as a fallback
            try:
                basic_message = {
                    "message": message,
                    "sender": sender,
                    "visitor_id": visitor_id
                }
                basic_result = supabase.table("messages").insert(basic_message).execute()
                if hasattr(basic_result, 'data') and len(basic_result.data) > 0:
                    logging.info(f"Logged chat message with minimal fields: {basic_result.data[0].get('id', 'unknown')}")
                    return True
                return False
            except Exception as basic_error:
                logging.error(f"Error logging even basic message: {basic_error}")
                return False
    
    except Exception as e:
        logging.error(f"Error in log_chat_message: {e}")
        return False

def get_chat_history(limit=50, visitor_id=None, target_user_id=None, chatbot_id=None):
    """Get chat history for a visitor and target user or chatbot
    
    Args:
        limit (int): Maximum number of messages to return
        visitor_id (str): Visitor ID to filter by
        target_user_id (str): Target user ID to filter by
        chatbot_id (str): Chatbot ID to filter by
        
    Returns:
        list: List of chat history items
    """
    try:
        if supabase is None:
            logging.warning("Supabase client not initialized, using in-memory messages")
            history = []
            
            # Filter messages from in_memory_messages matching the visitor_id
            if visitor_id and visitor_id in in_memory_messages:
                # Make a deep copy to avoid modifying the original
                history = copy.deepcopy(in_memory_messages[visitor_id])
                
                # Sort messages by timestamp
                history = sorted(
                    history,
                    key=lambda x: x.get("timestamp", "") if isinstance(x, dict) else "",
                    reverse=True  # newest messages first
                )
                
                # Apply limit
                history = history[:limit]
                
            return history
            
        logging.info(f"Getting chat history from Supabase: visitor_id={visitor_id}, target_user_id={target_user_id}, limit={limit}")
        
        # Build the query based on available parameters
        query = supabase.table("messages").select("*")
        
        # Add filters if provided
        if visitor_id:
            query = query.eq("visitor_id", visitor_id)
            
        if target_user_id:
            query = query.eq("user_id", target_user_id)
            
        if chatbot_id:
            query = query.eq("chatbot_id", chatbot_id)
            
        # Add ordering and limit
        results = query.order("created_at", desc=True).limit(limit).execute()
        
        # Extract and format the data
        if hasattr(results, 'data') and isinstance(results.data, list):
            history = results.data
            
            # Convert timestamps to string format for JSON serialization
            for item in history:
                if isinstance(item, dict):
                    # Ensure timestamp is in string format
                    if "created_at" in item and item["created_at"]:
                        item["timestamp"] = item["created_at"]
                        
            # Reverse to have oldest messages first for UI display
            history = list(reversed(history))
            
            logging.info(f"Found {len(history)} messages in history")
            return history
        else:
            logging.warning(f"Unexpected result format from Supabase: {type(results)}")
            return []
            
    except Exception as e:
        logging.error(f"Error fetching chat history: {e}")
        # Return empty history on error
        return []

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
                    print(f"Admin login successful for user: {username}")
                    return True
            
            print(f"Admin login failed for user: {username}")
            return False
        else:
            print("Supabase client not available, using default admin check")
            # Fallback for demo purposes - in production, always use the database
            return username == "admin" and password == "admin123"
    except Exception as e:
        print(f"Error verifying admin login: {e}")
        # Fallback for demo purposes
        return username == "admin" and password == "admin123"

def is_admin_user(user_id=None, email=None):
    """
    Check if a user is an admin based on user_id or email
    """
    try:
        if not supabase:
            print("Supabase client not available, admin check failed")
            return False
            
        if not user_id and not email:
            print("No user_id or email provided for admin check")
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
            print(f"Found admin user: {response.data[0]}")
            return True
            
        print(f"No admin user found for user_id={user_id}, email={email}")
        return False
    except Exception as e:
        print(f"Error checking admin user status: {e}")
        return False 