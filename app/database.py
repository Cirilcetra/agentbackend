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
            # For now, since we don't have a user_id column in the database,
            # return the first profile regardless of user_id
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
        
        return result
    except Exception as e:
        print(f"Error fetching profile data: {e}")
        return in_memory_profile.copy()

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
    Log a chat message to Supabase or in-memory storage
    """
    try:
        # Generate a UUID for the message
        message_id = str(uuid.uuid4())
        
        # Create message data with all required fields
        data = {
            "id": message_id,
            "message": message,
            "sender": sender,
            "response": response,
            "visitor_id": visitor_id or "anonymous",  # Ensure visitor_id is never None
            "visitor_name": visitor_name,
            "target_user_id": target_user_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        print(f"Logging chat message for visitor: {visitor_id}, name: {visitor_name}, target user: {target_user_id}")
        
        if supabase:
            # Log the data being sent to Supabase for debugging
            print(f"Sending to Supabase: {data}")
            
            try:
                # Try to insert the message using a more robust approach
                cleaned_data = {
                    # Include only fields that are likely in the Supabase schema
                    "id": message_id,
                    "message": message,
                    "sender": sender,
                    "response": response,
                    "visitor_id": visitor_id or "anonymous",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Only add optional fields if they have values
                if visitor_name:
                    cleaned_data["visitor_name"] = visitor_name
                if target_user_id:
                    cleaned_data["target_user_id"] = target_user_id
                
                response = supabase.table("messages").insert(cleaned_data).execute()
                
                if response.data:
                    print(f"Successfully logged message to Supabase. Response: {response.data}")
                    return response.data
                else:
                    print(f"No data returned from Supabase insert. Response: {response}")
                    print("Falling back to in-memory storage")
            except Exception as supabase_error:
                print(f"Supabase insert error: {supabase_error}")
                print("Falling back to in-memory storage due to Supabase error")
        else:
            print("Supabase client not available, using in-memory storage")
        
        # Add to in-memory storage if Supabase fails or is not available
        message_with_id = {**data, "id": message_id}
        in_memory_messages.append(message_with_id)
        print(f"Added message to in-memory storage with ID: {message_id}")
        
        # Debug: Print how many messages are in in-memory storage
        print(f"Total messages in in-memory storage: {len(in_memory_messages)}")
        
        return [message_with_id]
    except Exception as e:
        print(f"Error logging chat message: {e}")
        try:
            # Try to add to in-memory storage as fallback
            message_id = str(uuid.uuid4())
            message_with_id = {
                "id": message_id,
                "message": message,
                "sender": sender,
                "response": response,
                "visitor_id": visitor_id or "anonymous",
                "visitor_name": visitor_name,
                "target_user_id": target_user_id,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            in_memory_messages.append(message_with_id)
            print(f"Added message to in-memory storage after error with ID: {message_id}")
            return [message_with_id]
        except Exception as fallback_error:
            print(f"Error in fallback storage: {fallback_error}")
            return None

def get_chat_history(limit=50, visitor_id=None, target_user_id=None):
    """
    Get chat history from Supabase or in-memory storage
    Can filter by visitor_id and/or target_user_id
    """
    try:
        print(f"Getting chat history, limit: {limit}, visitor_id: {visitor_id}, target_user_id: {target_user_id}")
        
        # Initialize result array
        result_messages = []
        
        if supabase:
            try:
                query = supabase.table("messages").select("*").order("timestamp", desc=True)
                
                # Filter by visitor ID if provided
                if visitor_id:
                    print(f"Filtering chat history for visitor: {visitor_id}")
                    query = query.eq("visitor_id", visitor_id)
                
                # Filter by target user ID if provided
                if target_user_id:
                    print(f"Filtering chat history for target user: {target_user_id}")
                    query = query.eq("target_user_id", target_user_id)
                
                response = query.limit(limit).execute()
                
                if response.data:
                    print(f"Retrieved {len(response.data)} messages from Supabase")
                    # DEBUG: Print first message to verify visitor_id is present
                    if response.data and len(response.data) > 0:
                        print(f"First message visitor_id: {response.data[0].get('visitor_id', 'MISSING')}")
                    
                    # Add Supabase messages to result
                    result_messages.extend(response.data)
                else:
                    print("No chat history found in Supabase")
            except Exception as supabase_error:
                print(f"Error retrieving chat history from Supabase: {supabase_error}")
                print("Falling back to in-memory storage only")
        else:
            print("Supabase client not available, using in-memory storage only")
        
        # Add in-memory messages to the result (fallback or complementary)
        if in_memory_messages:
            print(f"Found {len(in_memory_messages)} messages in in-memory storage")
            
            # Filter in-memory messages
            filtered_messages = in_memory_messages
            
            # Apply filters if provided
            if visitor_id:
                filtered_messages = [msg for msg in filtered_messages if msg.get("visitor_id") == visitor_id]
                print(f"Filtered in-memory messages for visitor {visitor_id}: found {len(filtered_messages)} messages")
            
            if target_user_id:
                filtered_messages = [msg for msg in filtered_messages if msg.get("target_user_id") == target_user_id]
                print(f"Filtered in-memory messages for target user {target_user_id}: found {len(filtered_messages)} messages")
            
            # Add in-memory messages to result
            result_messages.extend(filtered_messages)
            
            # Debug: Print some information about the in-memory messages
            if filtered_messages:
                print(f"First in-memory message: {filtered_messages[0]}")
        
        # Sort by timestamp
        sorted_messages = sorted(
            result_messages, 
            key=lambda x: x.get("timestamp", ""), 
            reverse=True
        )
        
        # Limit the number of messages returned
        limited_messages = sorted_messages[:limit]
        
        print(f"Returning {len(limited_messages)} total messages (combined from Supabase and in-memory)")
        return limited_messages
    except Exception as e:
        print(f"Error getting chat history: {e}")
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