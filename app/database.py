import os
from supabase import create_client, Client
from dotenv import load_dotenv
import time
import json
import uuid

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
    Get the profile data from Supabase or in-memory storage
    If user_id is provided, try to match it with an existing profile
    Otherwise, return the default profile (first one found)
    """
    try:
        db_profile = None
        if supabase:
            if user_id:
                # Try to find a profile with the matching user_id
                response = supabase.table("profiles").select("*").eq("user_id", user_id).limit(1).execute()
                
                if response.data and len(response.data) > 0:
                    print(f"Found profile for user_id {user_id}: {response.data[0].get('id')}")
                    db_profile = response.data[0]
                else:
                    print(f"No profile found for user_id {user_id}, will create one")
                    # Create a new profile for this user
                    new_profile = DEFAULT_PROFILE.copy()
                    new_profile['user_id'] = user_id
                    inserted = supabase.table("profiles").insert(new_profile).execute()
                    if inserted.data and len(inserted.data) > 0:
                        print(f"Created new profile for user_id {user_id}: {inserted.data[0].get('id')}")
                        db_profile = inserted.data[0]
            else:
                # For backward compatibility, return the first profile if no user_id is specified
                response = supabase.table("profiles").select("*").limit(1).execute()
                
                if response.data and len(response.data) > 0:
                    print(f"Found profile: {response.data[0].get('id')}")
                    db_profile = response.data[0]
        
        # Merge the database profile with the in-memory profile
        # This ensures we have all fields available even if they're not in the database
        result = {}
        if db_profile:
            result.update(db_profile)
        
        # Add name and location from in-memory profile if not present
        if 'name' not in result and 'name' in in_memory_profile:
            result['name'] = in_memory_profile['name']
        
        if 'location' not in result and 'location' in in_memory_profile:
            result['location'] = in_memory_profile['location']
            
        # Add missing fields from in-memory profile
        for key in ['bio', 'skills', 'experience', 'projects', 'interests']:
            if key not in result or not result[key]:
                result[key] = in_memory_profile.get(key, '')
                
        # Add project_list from in-memory profile if not in result
        if 'project_list' not in result:
            result['project_list'] = in_memory_profile.get('project_list', [])
                
        # If we still don't have a result, use in-memory profile
        if not result:
            print("Using in-memory profile")
            result = in_memory_profile.copy()
            if user_id:
                result['user_id'] = user_id
        
        return result
    except Exception as e:
        print(f"Error fetching profile data: {e}")
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
    Update the profile data in Supabase or in-memory storage
    """
    try:
        if supabase:
            print(f"Attempting to update profile in Supabase: {data.get('id')}")
            
            # Get the first profile in the database to update
            response = supabase.table("profiles").select("*").limit(1).execute()
            
            existing_profile = None
            if response.data and len(response.data) > 0:
                existing_profile = response.data[0]
                data["id"] = existing_profile["id"]  # Ensure we're updating the right profile
                print(f"Found existing profile with ID: {existing_profile['id']}")
            
            profile_id = data.get("id")
            if profile_id:
                # Filter data to only include fields that exist in the database schema
                filtered_data = {}
                for key, value in data.items():
                    # Skip 'name', 'location', and 'project_list' if they're not in the existing profile
                    if key not in ['name', 'location', 'project_list'] or (existing_profile and key in existing_profile):
                        filtered_data[key] = value
                
                # Update existing profile
                print(f"Updating existing profile with ID: {profile_id}")
                print(f"Using filtered data: {filtered_data}")
                response = supabase.table("profiles").update(filtered_data).eq("id", profile_id).execute()
                print(f"Supabase update response: {response.data}")
            else:
                # Create new profile, but only with columns that exist
                print("Creating new profile in Supabase")
                # Start with basic fields that should exist in the database
                filtered_data = {
                    "bio": data.get("bio", ""),
                    "skills": data.get("skills", ""),
                    "experience": data.get("experience", ""),
                    "projects": data.get("projects", ""),
                    "interests": data.get("interests", "")
                }
                response = supabase.table("profiles").insert(filtered_data).execute()
                print(f"Supabase insert response: {response.data}")
            
            if response.data:
                print("Successfully updated profile in Supabase")
                
        # Update in-memory profile (to ensure we have all fields)
        for key, value in data.items():
            if key != 'id':  # Don't overwrite id
                in_memory_profile[key] = value
        
        # For project_list, we need to handle it specially if it was included
        if 'project_list' in data:
            in_memory_profile['project_list'] = data['project_list']
        
        # Save updated profile to file for persistence
        save_profile_to_file()
        
        return data
    except Exception as e:
        print(f"Error updating profile: {e}")
        
        # Fallback to in-memory update if Supabase fails
        for key, value in data.items():
            if key != 'id':  # Don't overwrite id
                in_memory_profile[key] = value
                
        # Save updated profile to file for persistence
        save_profile_to_file()
        
        return data

def add_project(project_data, user_id=None):
    """
    Add a new project to the project list
    """
    try:
        profile_data = get_profile_data(user_id)
        
        # Ensure project_list exists
        if 'project_list' not in profile_data:
            profile_data['project_list'] = []
        
        # Generate a UUID for the project if not provided
        if not project_data.get('id'):
            project_data['id'] = str(uuid.uuid4())
        
        # Set creation timestamp
        project_data['created_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        project_data['updated_at'] = project_data['created_at']
        
        # Extract HTML content if available in Lexical format
        if project_data.get('content') and not project_data.get('content_html'):
            try:
                content_data = json.loads(project_data['content'])
                if content_data.get('html'):
                    project_data['content_html'] = content_data['html']
            except (json.JSONDecodeError, KeyError):
                print(f"Warning: Could not extract HTML from project content")
        
        # Add project to list
        profile_data['project_list'].append(project_data)
        
        # Update profile data
        return update_profile_data(profile_data, user_id)
    except Exception as e:
        print(f"Error adding project: {e}")
        return None

def update_project(project_id, project_data, user_id=None):
    """
    Update an existing project
    """
    try:
        profile_data = get_profile_data(user_id)
        
        # Ensure project_list exists
        if 'project_list' not in profile_data:
            profile_data['project_list'] = []
            return None  # Project not found
        
        # Find the project by ID
        for i, project in enumerate(profile_data['project_list']):
            if project.get('id') == project_id:
                # Preserve the ID and created_at timestamp
                project_data['id'] = project_id
                if 'created_at' in project:
                    project_data['created_at'] = project['created_at']
                
                # Update the updated_at timestamp
                project_data['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                
                # Extract HTML content if available in Lexical format
                if project_data.get('content') and not project_data.get('content_html'):
                    try:
                        content_data = json.loads(project_data['content'])
                        if content_data.get('html'):
                            project_data['content_html'] = content_data['html']
                    except (json.JSONDecodeError, KeyError):
                        print(f"Warning: Could not extract HTML from project content")
                
                # Update the project
                profile_data['project_list'][i] = project_data
                
                # Update profile data
                return update_profile_data(profile_data, user_id)
        
        return None  # Project not found
    except Exception as e:
        print(f"Error updating project: {e}")
        return None

def delete_project(project_id, user_id=None):
    """
    Delete a project
    """
    try:
        profile_data = get_profile_data(user_id)
        
        # Ensure project_list exists
        if 'project_list' not in profile_data:
            profile_data['project_list'] = []
            return False  # Project not found
        
        # Find the project by ID
        for i, project in enumerate(profile_data['project_list']):
            if project.get('id') == project_id:
                # Remove the project
                profile_data['project_list'].pop(i)
                
                # Update profile data
                update_profile_data(profile_data, user_id)
                return True
        
        return False  # Project not found
    except Exception as e:
        print(f"Error deleting project: {e}")
        return False

def log_chat_message(message, sender, response=None, visitor_id=None, visitor_name=None, target_user_id=None):
    """
    Log a chat message to the database
    Params:
        message: the message to log
        sender: who sent the message (e.g., "user", "assistant")
        response: optional response to the message
        visitor_id: unique identifier for the visitor/chat session
        visitor_name: optional name for the visitor
        target_user_id: optional target user ID for user-specific chatbots
    """
    try:
        timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        
        # Create message data
        message_data = {
            "id": str(uuid.uuid4()),
            "message": message,
            "sender": sender,
            "response": response,
            "timestamp": timestamp,
        }
        
        # Add visitor ID if provided
        if visitor_id:
            message_data["visitor_id"] = visitor_id
            
        # Add visitor name if provided
        if visitor_name:
            message_data["visitor_name"] = visitor_name
            
        # Add target user ID if provided
        if target_user_id:
            message_data["target_user_id"] = target_user_id
            
        saved_messages = []
        
        if supabase:
            try:
                # Store in Supabase
                print(f"Storing chat message in Supabase. Visitor: {visitor_id}, Target User: {target_user_id}")
                # Use the messages table (or chat_history)
                insert_response = supabase.table("chat_history").insert(message_data).execute()
                
                if insert_response.data:
                    print(f"Successfully saved chat message to Supabase: {insert_response.data[0].get('id')}")
                    saved_messages = insert_response.data
                else:
                    print("Failed to save chat message to Supabase, falling back to in-memory storage")
                    in_memory_messages.append(message_data)
                    saved_messages = [message_data]
            except Exception as db_error:
                print(f"Error saving to Supabase: {db_error}")
                print("Falling back to in-memory storage")
                in_memory_messages.append(message_data)
                saved_messages = [message_data]
        else:
            # Store in-memory
            print("Supabase not available, storing chat message in-memory")
            in_memory_messages.append(message_data)
            saved_messages = [message_data]
            
        return saved_messages
    except Exception as e:
        print(f"Error logging chat message: {e}")
        # Best effort: Try to save to in-memory storage anyway
        try:
            message_data = {
                "id": str(uuid.uuid4()),
                "message": message,
                "sender": sender,
                "response": response,
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                "visitor_id": visitor_id,
                "visitor_name": visitor_name,
                "target_user_id": target_user_id
            }
            in_memory_messages.append(message_data)
            return [message_data]
        except:
            return None

def get_chat_history(limit=50, visitor_id=None, target_user_id=None):
    """
    Get the chat history from Supabase or in-memory storage
    Params:
        limit: Maximum number of messages to return
        visitor_id: If provided, filter by visitor_id
        target_user_id: If provided, filter by target_user_id (the user whose profile was used for the responses)
    """
    try:
        if supabase:
            # Start building the query
            query = supabase.table("chat_history").select("*").order('timestamp', desc=True)
            
            # Apply filters if provided
            if visitor_id:
                query = query.eq("visitor_id", visitor_id)
                
            # Only add target_user_id filter if it's provided and not None/empty
            if target_user_id:
                print(f"Filtering chat history by target_user_id: {target_user_id}")
                query = query.eq("target_user_id", target_user_id)
            
            # Add limit and execute
            response = query.limit(limit).execute()
            
            if response.data:
                print(f"Found {len(response.data)} chat history items in database")
                return response.data
            
        # Fallback to in-memory storage if Supabase returns no data or isn't available
        if visitor_id or target_user_id:
            filtered_messages = in_memory_messages.copy()
            
            if visitor_id:
                filtered_messages = [msg for msg in filtered_messages if msg.get("visitor_id") == visitor_id]
                
            if target_user_id:
                filtered_messages = [msg for msg in filtered_messages if msg.get("target_user_id") == target_user_id]
                
            # Sort by timestamp (newest first) and apply limit
            filtered_messages.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return filtered_messages[:limit]
        else:
            # Sort by timestamp (newest first) and apply limit
            sorted_messages = sorted(in_memory_messages, key=lambda x: x.get("timestamp", ""), reverse=True)
            return sorted_messages[:limit]
    except Exception as e:
        print(f"Error fetching chat history: {e}")
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