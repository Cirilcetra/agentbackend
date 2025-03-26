import os
from supabase import create_client, Client
from dotenv import load_dotenv
import time
import json
import uuid
import logging
import copy
import re

# Import auth headers getter (will be dynamically populated during requests)
try:
    from app.routes.auth import get_auth_headers
except ImportError:
    # Define a fallback for circular imports or when running during startup
    def get_auth_headers():
        return {}

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
        # Create Supabase client with additional configuration
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Test the connection to make sure it's working
        try:
            # Try a simple query to test the connection
            test_response = supabase.table("profiles").select("count", count="exact").limit(1).execute()
            count = test_response.count if hasattr(test_response, 'count') else 0
            logging.info(f"Supabase connection initialized successfully. Found {count} profiles.")
        except Exception as test_error:
            logging.error(f"Supabase connection test failed: {test_error}")
            logging.warning("Proceeding with Supabase client, but there may be connectivity issues.")
    else:
        logging.warning("Missing Supabase environment variables. Using in-memory storage.")
except Exception as e:
    logging.error(f"Error initializing Supabase client: {e}")
    logging.warning("Using in-memory storage instead.")

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

in_memory_messages = {}

def get_profile_data(user_id=None):
    """
    Get the profile data from Supabase for a specific user
    
    Args:
        user_id (str): User ID from auth.users.id
        
    Returns:
        dict: Profile data dictionary with user information
    """
    try:
        if not user_id:
            logging.warning("No user_id provided to get_profile_data, using default profile data")
            # Return a copy of the default in-memory profile to avoid modification
            default_profile = in_memory_profile.copy()
            default_profile['is_default'] = True
            return default_profile
            
        if supabase is None:
            logging.warning("Supabase client not available, using default profile with user_id")
            # Return a copy of the default profile with the user_id added
            profile = in_memory_profile.copy()
            profile['user_id'] = user_id
            profile['is_default'] = True
            return profile
            
        # Query for the specific user's profile
        logging.info(f"Querying Supabase for profile with user_id: {user_id}")
        response = None
        
        try:
            # Make sure we're explicitly filtering by user_id
            response = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
            logging.info(f"Profile query result: {len(response.data) if response and hasattr(response, 'data') else 'No data'} records found")
        except Exception as query_error:
            logging.error(f"Error querying profiles table: {query_error}")
            response = None
        
        if response and response.data and len(response.data) > 0:
            logging.info(f"Found profile for user: {user_id}")
            profile = response.data[0]
            profile['is_default'] = False  # Indicate this is a real profile
            
            # Define default values to use only when fields are missing or null
            default_values = {
                'bio': 'I am a software engineer with a passion for building AI and web applications.',
                'skills': 'JavaScript, TypeScript, React, Node.js, Python',
                'experience': '5+ years of experience in software development',
                'interests': 'AI, web development, reading',
                'name': 'New User',
                'location': 'Worldwide',
                'projects': 'AI-powered applications'
            }
            
            # Only apply defaults for fields that are truly missing or null
            for field, default_value in default_values.items():
                if field not in profile or profile[field] is None:
                    # Only use the default for truly missing/null fields
                    profile[field] = default_value
                    logging.debug(f"Applied default value for missing/null field: {field}")
                elif isinstance(profile[field], str) and profile[field].strip() == '':
                    # Only use default for empty strings
                    profile[field] = default_value
                    logging.debug(f"Applied default value for empty field: {field}")
            
            # Initialize empty project list if not present
            if 'project_list' not in profile:
                profile['project_list'] = []
                
            # Fetch user's projects
            try:
                projects_response = supabase.table("projects").select("*").eq("user_id", user_id).execute()
                
                if projects_response.data and len(projects_response.data) > 0:
                    logging.info(f"Found {len(projects_response.data)} projects for user: {user_id}")
                    profile['project_list'] = projects_response.data
            except Exception as project_error:
                logging.error(f"Error fetching projects: {project_error}")
                    
            return profile
        else:
            logging.warning(f"No profile found for user: {user_id}, creating a new default profile")
            # If no profile found for this user, create one in Supabase
            try:
                # Create a new profile for this user
                new_profile = {
                    'user_id': user_id,
                    'bio': in_memory_profile.get('bio', 'I am a software engineer with a passion for building AI and web applications.'),
                    'skills': in_memory_profile.get('skills', 'JavaScript, TypeScript, React, Node.js, Python'),
                    'experience': in_memory_profile.get('experience', '5+ years of experience in software development'),
                    'interests': in_memory_profile.get('interests', 'AI, web development, reading'),
                    'name': 'New User',
                    'location': 'Worldwide',
                    'projects': in_memory_profile.get('projects', 'AI-powered applications'),
                    'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }
                
                create_response = supabase.table("profiles").insert(new_profile).execute()
                
                if create_response.data and len(create_response.data) > 0:
                    logging.info(f"Created new profile for user: {user_id}")
                    created_profile = create_response.data[0]
                    created_profile['project_list'] = []
                    created_profile['is_default'] = False
                    return created_profile
            except Exception as create_error:
                logging.error(f"Error creating new profile: {create_error}")
            
            # If creation failed, return a default profile with the user_id
            default_profile = in_memory_profile.copy()
            default_profile['user_id'] = user_id
            default_profile['project_list'] = []
            default_profile['is_default'] = True
            default_profile['name'] = 'New User'
            default_profile['location'] = 'Worldwide'
            return default_profile
    except Exception as e:
        logging.error(f"Error fetching profile data: {e}")
        # Return default profile on error
        default_profile = in_memory_profile.copy()
        if user_id:
            default_profile['user_id'] = user_id
        default_profile['project_list'] = []
        default_profile['is_default'] = True
        default_profile['name'] = 'New User'
        default_profile['location'] = 'Worldwide'
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
    
    Args:
        data (dict): Profile data to update
        user_id (str): User ID from auth.users.id
        
    Returns:
        dict: Updated profile data with success status or None on error
    """
    try:
        if not user_id:
            logging.error("Error: No user_id provided for profile update")
            return {"success": False, "profile": None, "message": "User ID is required"}
            
        if supabase is None:
            logging.warning("Supabase client not available, using in-memory storage")
            # Fallback to in-memory update
            for key, value in data.items():
                if key != 'id':  # Don't overwrite id
                    in_memory_profile[key] = value
            
            # Save updated profile to file for persistence
            save_profile_to_file()
            
            # Return a copy of the updated profile
            updated_profile = in_memory_profile.copy()
            updated_profile['user_id'] = user_id
            updated_profile['is_default'] = True
            return {"success": True, "profile": updated_profile, "message": "Profile updated successfully (in-memory)"}
            
        logging.info(f"Updating profile for user: {user_id}")
        
        # Check if profile exists for this user
        try:
            # Get auth headers for authenticated requests
            auth_headers = get_auth_headers()
            logging.debug(f"Using auth headers: {bool(auth_headers)}")
            
            response = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
            logging.info(f"Found {len(response.data) if response and hasattr(response, 'data') and response.data else 0} profiles for user: {user_id}")
        
            # Prepare profile data (exclude project_list which is stored separately)
            profile_data = {k: v for k, v in data.items() if k != 'project_list' and k != 'id' and k != 'is_default'}
            
            # Convert empty strings to None (NULL in database)
            for key, value in profile_data.items():
                if isinstance(value, str) and value.strip() == '':
                    profile_data[key] = None
                    logging.info(f"Converting empty string to NULL for field: {key}")
                    
            profile_data['user_id'] = user_id
            profile_data['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            
            logging.info(f"Profile data to update: {profile_data}")
            
            if response.data and len(response.data) > 0:
                # Update existing profile
                existing_profile = response.data[0]
                profile_id = existing_profile['id']
                
                logging.info(f"Updating existing profile with ID: {profile_id}")
                try:
                    # IMPORTANT: Update the profile using user_id, not profile ID
                    logging.info(f"Updating profile with user_id: {user_id}")
                    logging.debug(f"Data being sent to Supabase: {profile_data}")
                    
                    # Log existing data for comparison
                    logging.info(f"Existing profile data: {existing_profile}")
                    
                    # Execute the update
                    update_response = supabase.table("profiles").update(profile_data).eq("user_id", user_id).execute()
                    
                    if not (update_response.data and len(update_response.data) > 0):
                        logging.error(f"Failed to update profile: {update_response}")
                        return {"success": False, "profile": None, "message": "Failed to update profile in database"}
                    
                    logging.info(f"Profile updated successfully by user_id")
                    logging.debug(f"Update response: {update_response.data[0] if update_response.data else None}")
                    
                    # Get the updated profile data
                    updated_profile_response = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
                    if updated_profile_response.data and len(updated_profile_response.data) > 0:
                        updated_profile = updated_profile_response.data[0]
                        logging.info(f"Retrieved updated profile: {updated_profile}")
                    else:
                        # Fallback to the profile data we have
                        updated_profile = profile_data
                        logging.warning("Could not retrieve updated profile, using profile_data as fallback")
                    
                    # Success
                    return {
                        "success": True,
                        "profile": updated_profile,
                        "message": "Profile updated successfully"
                    }
                except Exception as update_error:
                    # Log the error and try using the old method as fallback
                    logging.error(f"Error updating profile by user_id: {update_error}")
                    try:
                        # Try updating by profile ID as fallback
                        update_response = supabase.table("profiles").update(profile_data).eq("id", profile_id).execute()
                        
                        if not (update_response.data and len(update_response.data) > 0):
                            logging.error(f"Failed to update profile by ID as fallback: {update_response}")
                            return {"success": False, "profile": None, "message": "Failed to update profile in database"}
                        
                        logging.info(f"Profile updated successfully by profile ID (fallback)")
                        
                        # Get the updated profile data
                        updated_profile_response = supabase.table("profiles").select("*").eq("id", profile_id).execute()
                        if updated_profile_response.data and len(updated_profile_response.data) > 0:
                            updated_profile = updated_profile_response.data[0]
                        else:
                            # Fallback to the profile data we have
                            updated_profile = profile_data
                        
                        # Return success with the updated profile
                        return {
                            "success": True,
                            "profile": updated_profile,
                            "message": "Profile updated successfully (by ID fallback)"
                        }
                    except Exception as fallback_error:
                        logging.error(f"Error updating profile by ID fallback: {fallback_error}")
                        return {"success": False, "profile": None, "message": f"Failed to update profile: {str(fallback_error)}"}
            else:
                # Create new profile
                logging.info(f"Creating new profile for user: {user_id}")
                
                # Add created_at for new profiles
                profile_data['created_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                
                create_response = supabase.table("profiles").insert(profile_data).execute()
                
                if not (create_response.data and len(create_response.data) > 0):
                    logging.error(f"Failed to create profile: {create_response}")
                    return {"success": False, "profile": None, "message": "Failed to create profile in database"}
                    
                logging.info(f"Profile created successfully")
                
                # Return the newly created profile
                created_profile = create_response.data[0] if (create_response.data and len(create_response.data) > 0) else profile_data
                return {
                    "success": True,
                    "profile": created_profile,
                    "message": "New profile created successfully"
                }
        except Exception as e:
            logging.error(f"Error checking or updating profile: {e}")
            return {"success": False, "profile": None, "message": f"Error updating profile: {str(e)}"}
        
        # Handle project_list if provided
        if 'project_list' in data and data['project_list']:
            try:
                logging.info(f"Updating {len(data['project_list'])} projects")
                for project in data['project_list']:
                    if 'id' in project and project['id']:
                        # Update existing project
                        project_result = update_project(project['id'], project, user_id)
                        if not project_result:
                            logging.warning(f"Failed to update project: {project['id']}")
                    else:
                        # Add new project
                        project_result = add_project(project, user_id)
                        if not project_result:
                            logging.warning(f"Failed to add new project")
            except Exception as project_error:
                logging.error(f"Error handling project list: {project_error}")
                # Continue with the update - don't fail the entire operation
        
        # Get the updated profile to return (unless we've already returned)
        try:
            updated_profile = get_profile_data(user_id)
            updated_profile['is_default'] = False  # This is now a real profile
            return {"success": True, "profile": updated_profile, "message": "Profile updated successfully"}
        except Exception as final_error:
            logging.error(f"Error getting final updated profile: {final_error}")
            # Return the minimal profile data we have
            return {"success": True, "profile": profile_data, "message": "Profile updated but retrieval failed"}
        
    except Exception as e:
        logging.error(f"Error updating profile: {e}", exc_info=True)
        return {"success": False, "profile": None, "message": f"Error updating profile: {str(e)}"}

def add_project(project_data, user_id=None):
    """
    Add a new project to the database
    
    Args:
        project_data (dict): Project data to add
        user_id (str): User ID from auth.users.id
        
    Returns:
        dict: Updated profile data with success status or None on error
    """
    try:
        if not user_id:
            logging.error("Error: user_id is required to add a project")
            return {"success": False, "message": "User ID is required to add a project", "profile": None}
            
        # Generate a UUID for the project if not provided
        if not project_data.get('id'):
            project_data['id'] = str(uuid.uuid4())
            logging.info(f"Generated new project ID: {project_data['id']}")
        
        # Set timestamps
        current_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        project_data['created_at'] = current_time
        project_data['updated_at'] = current_time
        
        # Add user_id to the project data
        project_data['user_id'] = user_id
        
        # Log the complete project data
        logging.info(f"Adding project with data: {project_data}")
        
        # Validate required fields
        required_fields = ["title", "description"]
        missing_fields = [field for field in required_fields if not project_data.get(field)]
        
        if missing_fields:
            logging.error(f"Missing required fields for project: {missing_fields}")
            return {"success": False, "message": f"Missing required fields: {', '.join(missing_fields)}", "profile": None}
        
        if supabase:
            try:
                # Insert project into projects table
                logging.info(f"Inserting project into Supabase database")
                response = supabase.table("projects").insert(project_data).execute()
                
                if not (response and hasattr(response, 'data') and response.data and len(response.data) > 0):
                    logging.error(f"Failed to add project to database: Empty response")
                    # Fall back to in-memory storage if database fails
                    logging.info("Falling back to in-memory storage")
                    return add_project_in_memory(project_data, user_id)
                    
                logging.info(f"Added new project with ID: {project_data['id']} for user: {user_id}")
                
                # Get the created project from the response
                created_project = response.data[0]
                logging.info(f"Created project: {created_project}")
                
                # Return the updated profile data
                updated_profile = get_profile_data(user_id)
                
                # Make sure the newly created project is in the project list
                if 'project_list' not in updated_profile:
                    updated_profile['project_list'] = []
                
                # Check if the project is already in the list
                project_exists = False
                for i, project in enumerate(updated_profile['project_list']):
                    if project.get('id') == created_project['id']:
                        updated_profile['project_list'][i] = created_project
                        project_exists = True
                        break
                
                if not project_exists:
                    updated_profile['project_list'].append(created_project)
                
                return {"success": True, "message": "Project added successfully", "profile": updated_profile}
                
            except Exception as db_error:
                logging.error(f"Database error adding project: {db_error}", exc_info=True)
                # Fall back to in-memory storage
                logging.info("Falling back to in-memory storage after database error")
                return add_project_in_memory(project_data, user_id)
        
        # Fallback to in-memory storage
        logging.warning("Supabase is not available, using in-memory storage")
        return add_project_in_memory(project_data, user_id)
        
    except Exception as e:
        logging.error(f"Error adding project: {e}", exc_info=True)
        return {"success": False, "message": f"Error adding project: {str(e)}", "profile": None}

def add_project_in_memory(project_data, user_id=None):
    """
    Add a project to in-memory storage (helper function)
    """
    try:
        logging.info(f"Adding project to in-memory storage: {project_data}")
        
        if 'project_list' not in in_memory_profile:
            in_memory_profile['project_list'] = []
            
        # Make a copy of the project data to avoid modifying the original
        project_copy = project_data.copy()
        
        # Make sure it has an ID
        if not project_copy.get('id'):
            project_copy['id'] = str(uuid.uuid4())
            
        # Check if the project already exists (by ID)
        for i, project in enumerate(in_memory_profile['project_list']):
            if project.get('id') == project_copy.get('id'):
                # Update existing project
                in_memory_profile['project_list'][i] = project_copy
                logging.info(f"Updated existing project with ID: {project_copy['id']}")
                save_profile_to_file()
                
                updated_profile = in_memory_profile.copy()
                updated_profile['user_id'] = user_id
                return {"success": True, "message": "Project updated successfully (in-memory)", "profile": updated_profile}
        
        # Add as new project
        in_memory_profile['project_list'].append(project_copy)
        logging.info(f"Added new project with ID: {project_copy['id']}")
        save_profile_to_file()
        
        updated_profile = in_memory_profile.copy()
        updated_profile['user_id'] = user_id
        return {"success": True, "message": "Project added successfully (in-memory)", "profile": updated_profile}
    
    except Exception as e:
        logging.error(f"Error adding project to in-memory storage: {e}", exc_info=True)
        return {"success": False, "message": f"Error adding project in-memory: {str(e)}", "profile": None}

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
        visitor_id (str): Optional visitor ID for anonymous visitors
        visitor_name (str): Optional visitor name
        target_user_id (str): User ID from auth.users.id
        chatbot_id (str): Optional chatbot ID
        
    Returns:
        bool: True if the message was logged successfully
    """
    try:
        # Generate timestamp for the message
        timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        
        # Add created_at field for database compatibility
        created_at = timestamp
        
        # Use a default visitor ID if none provided
        if not visitor_id:
            visitor_id = f"anonymous-{int(time.time())}"
            logging.info(f"Generated anonymous visitor_id: {visitor_id}")
        
        logging.info(f"Logging chat message for user_id: {target_user_id}, visitor_id: {visitor_id}")
        logging.info(f"Message: {message[:50]}... Response: {response[:50] if response else 'None'}")
        
        # Handle in-memory storage if Supabase is unavailable
        if supabase is None:
            logging.warning("Supabase client not initialized, using in-memory messages")
            
            # Initialize the visitor's message list if it doesn't exist
            if visitor_id not in in_memory_messages:
                in_memory_messages[visitor_id] = []
                
            # Add the message to the in-memory messages
            message_data = {
                "id": str(uuid.uuid4()),
                "message": message,
                "response": response if response else "",
                "sender": sender,
                "visitor_id": visitor_id,
                "visitor_name": visitor_name if visitor_name else "Anonymous",
                "user_id": target_user_id,
                "chatbot_id": chatbot_id,
                "created_at": created_at
            }
            
            in_memory_messages[visitor_id].append(message_data)
            logging.info(f"Added message to in-memory messages for visitor: {visitor_id}")
            
            # Log all in-memory messages for this visitor
            logging.info(f"Current in-memory messages for visitor {visitor_id}: {len(in_memory_messages[visitor_id])}")
            
            return True
        
        # Create a message record for Supabase
        message_data = {
            "message": message,
            "response": response if response else "",
            "visitor_id": visitor_id,
            "created_at": created_at
        }
        
        # Add optional fields if available
        if visitor_name:
            message_data["visitor_name"] = visitor_name
            
        # For authenticated users - crucial for RLS
        if target_user_id:
            message_data["user_id"] = target_user_id
        
        # Only add chatbot_id if a valid one is provided
        if chatbot_id:
            message_data["chatbot_id"] = chatbot_id
        
        # For an authenticated user, first check if they have a public chatbot
        # This helps with the RLS policy for messages
        if target_user_id and not chatbot_id:
            try:
                logging.info(f"Looking for a public chatbot for user: {target_user_id}")
                # Find a public chatbot for this user
                public_chatbot_query = supabase.table("chatbots") \
                    .select("id") \
                    .eq("user_id", target_user_id) \
                    .eq("is_public", True) \
                    .limit(1) \
                    .execute()
                    
                if public_chatbot_query.data and len(public_chatbot_query.data) > 0:
                    message_data["chatbot_id"] = public_chatbot_query.data[0]["id"]
                    logging.info(f"Using public chatbot {message_data['chatbot_id']} for message")
                else:
                    logging.info("No public chatbot found, creating a default one")
                    # Create a default public chatbot for this user
                    default_chatbot = {
                        "user_id": target_user_id,
                        "name": "Portfolio Assistant",
                        "description": "Default portfolio assistant",
                        "is_public": True,
                        "created_at": created_at,
                        "updated_at": created_at
                    }
                    chatbot_result = supabase.table("chatbots").insert(default_chatbot).execute()
                    if chatbot_result.data and len(chatbot_result.data) > 0:
                        message_data["chatbot_id"] = chatbot_result.data[0]["id"]
                        logging.info(f"Created and using new chatbot {message_data['chatbot_id']} for message")
            except Exception as chatbot_error:
                logging.error(f"Error finding/creating chatbot: {chatbot_error}")
        
        # Insert message into Supabase
        try:
            logging.info(f"Inserting message into Supabase: {message_data}")
            result = supabase.table("messages").insert(message_data).execute()
            
            if hasattr(result, 'data') and len(result.data) > 0:
                logging.info(f"Successfully logged chat message to Supabase: {result.data[0].get('id', 'unknown')}")
                return True
            else:
                logging.warning(f"Unexpected result format when logging message: {result}")
                # Fall back to in-memory storage
                return log_message_in_memory(message, sender, response, visitor_id, visitor_name, target_user_id, chatbot_id, created_at)
                
        except Exception as insert_error:
            logging.error(f"Error logging chat message: {insert_error}")
            
            # If the issue is RLS policy, try inserting with minimal required fields
            if "'42501'" in str(insert_error) or "violates row-level security policy" in str(insert_error):
                logging.warning("RLS policy violation, trying with minimal fields")
                
                # For anonymous users, try without user_id and chatbot_id
                if not target_user_id:
                    try:
                        minimal_data = {
                            "message": message,
                            "response": response if response else "",
                            "sender": sender,
                            "visitor_id": visitor_id,
                            "created_at": created_at
                        }
                        
                        anon_result = supabase.table("messages").insert(minimal_data).execute()
                        if hasattr(anon_result, 'data') and len(anon_result.data) > 0:
                            logging.info(f"Successfully logged anonymous message with minimal fields")
                            return True
                    except Exception as anon_error:
                        logging.error(f"Failed even with minimal anonymous fields: {anon_error}")
                
                # For authenticated users, we need to ensure RLS compliance
                elif target_user_id:
                    try:
                        # Adjust the policy in Supabase to allow this
                        auth_minimal_data = {
                            "message": message,
                            "response": response if response else "",
                            "sender": sender,
                            "visitor_id": visitor_id,
                            "user_id": target_user_id,
                            "created_at": created_at
                        }
                        
                        auth_result = supabase.table("messages").insert(auth_minimal_data).execute()
                        if hasattr(auth_result, 'data') and len(auth_result.data) > 0:
                            logging.info(f"Successfully logged authenticated message with minimal fields")
                            return True
                    except Exception as auth_error:
                        logging.error(f"Failed even with minimal authenticated fields: {auth_error}")
            
            # If all attempts failed, log to in-memory as fallback
            return log_message_in_memory(message, sender, response, visitor_id, visitor_name, target_user_id, chatbot_id, created_at)
    
    except Exception as e:
        logging.error(f"Error in log_chat_message: {e}")
        # Try in-memory as last resort
        return log_message_in_memory(message, sender, response, visitor_id, visitor_name, target_user_id, chatbot_id)

def log_message_in_memory(message, sender="user", response=None, visitor_id=None, visitor_name=None, target_user_id=None, chatbot_id=None, created_at=None):
    """Helper function to log messages in memory when database fails"""
    try:
        if not created_at:
            created_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            
        if not visitor_id:
            visitor_id = f"anonymous-{int(time.time())}"
            
        logging.warning("Falling back to in-memory storage for chat message")
        
        if visitor_id not in in_memory_messages:
            in_memory_messages[visitor_id] = []
            
        fallback_data = {
            "id": str(uuid.uuid4()),
            "message": message,
            "response": response if response else "",
            "sender": sender,
            "visitor_id": visitor_id,
            "visitor_name": visitor_name if visitor_name else "Anonymous",
            "user_id": target_user_id,
            "chatbot_id": chatbot_id,
            "created_at": created_at
        }
            
        in_memory_messages[visitor_id].append(fallback_data)
        logging.info(f"Added message to in-memory fallback storage for visitor: {visitor_id}")
        
        # Log the number of messages now in memory
        logging.info(f"Current in-memory messages for visitor {visitor_id}: {len(in_memory_messages[visitor_id])}")
        
        return True
    except Exception as fallback_error:
        logging.error(f"Error in fallback in-memory message storage: {fallback_error}")
        return False

def get_chat_history(limit=50, visitor_id=None, target_user_id=None, chatbot_id=None):
    """
    Get chat history for a visitor and target user
    
    Args:
        limit (int): Maximum number of messages to return
        visitor_id (str): Optional visitor ID to filter by
        target_user_id (str): Optional target user ID to filter by (auth.users.id)
        chatbot_id (str): Optional chatbot ID to filter by
        
    Returns:
        list: List of chat history items
    """
    try:
        logging.info(f"Getting chat history: visitor_id={visitor_id}, target_user_id={target_user_id}, chatbot_id={chatbot_id}")
        
        if supabase is None:
            logging.warning("Supabase client not initialized, using in-memory messages")
            history = []
            
            # Filter messages from in_memory_messages matching the visitor_id
            if visitor_id and visitor_id in in_memory_messages:
                # Make a deep copy to avoid modifying the original
                logging.info(f"Found {len(in_memory_messages[visitor_id])} in-memory messages for visitor: {visitor_id}")
                history = copy.deepcopy(in_memory_messages[visitor_id])
                
                # Sort messages by timestamp/created_at
                history = sorted(
                    history,
                    key=lambda x: x.get("created_at", "") or x.get("timestamp", ""),
                    reverse=True  # newest messages first
                )
                
                # Apply limit
                history = history[:limit]
                
                logging.info(f"Returning {len(history)} in-memory chat messages")
                
            return history
        
        # Use Supabase to get chat history    
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
        query = query.order("created_at", desc=True).limit(limit)
        
        # Execute the query
        try:
            result = query.execute()
            
            if result and hasattr(result, 'data'):
                logging.info(f"Retrieved {len(result.data)} chat messages from database")
                return result.data
            else:
                logging.warning("No chat history found in database")
                return []
                
        except Exception as query_error:
            logging.error(f"Error querying chat history: {query_error}")
            
            # Try again with just visitor_id if other parameters might be causing RLS issues
            if (target_user_id or chatbot_id) and visitor_id:
                try:
                    logging.info("Retrying with only visitor_id filter")
                    simple_query = supabase.table("messages").select("*").eq("visitor_id", visitor_id).order("created_at", desc=True).limit(limit)
                    simple_result = simple_query.execute()
                    
                    if simple_result and hasattr(simple_result, 'data'):
                        logging.info(f"Retrieved {len(simple_result.data)} chat messages with simplified query")
                        return simple_result.data
                except Exception as simple_error:
                    logging.error(f"Error with simplified chat history query: {simple_error}")
            
            # Fall back to in-memory if all database attempts fail
            return get_in_memory_chat_history(limit, visitor_id, target_user_id, chatbot_id)
            
    except Exception as e:
        logging.error(f"Error fetching chat history: {e}")
        return get_in_memory_chat_history(limit, visitor_id, target_user_id, chatbot_id)

def get_in_memory_chat_history(limit=50, visitor_id=None, target_user_id=None, chatbot_id=None):
    """Helper function to get in-memory chat history when database fails"""
    try:
        history = []
        
        # Filter messages from in_memory_messages matching the visitor_id
        if visitor_id and visitor_id in in_memory_messages:
            logging.info(f"Using in-memory chat history for visitor: {visitor_id}")
            # Make a deep copy to avoid modifying the original
            candidate_messages = copy.deepcopy(in_memory_messages[visitor_id])
            
            # Apply any additional filters
            if target_user_id:
                candidate_messages = [msg for msg in candidate_messages 
                                     if msg.get("user_id") == target_user_id]
                                     
            if chatbot_id:
                candidate_messages = [msg for msg in candidate_messages 
                                     if msg.get("chatbot_id") == chatbot_id]
            
            # Sort messages by timestamp/created_at
            candidate_messages = sorted(
                candidate_messages,
                key=lambda x: x.get("created_at", "") or x.get("timestamp", ""),
                reverse=True  # newest messages first
            )
            
            # Apply limit
            history = candidate_messages[:limit]
            
            logging.info(f"Returning {len(history)} in-memory chat messages as fallback")
            
        return history
    except Exception as fallback_error:
        logging.error(f"Error in fallback in-memory chat history: {fallback_error}")
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

def update_profile_in_memory_only(data, user_id=None):
    """
    Update only the in-memory profile and save to file, bypassing Supabase
    This is useful when RLS policies prevent database updates
    
    Args:
        data (dict): Profile data to update
        user_id (str): User ID from auth.users.id
        
    Returns:
        dict: Updated profile data with success status
    """
    try:
        # Make a local copy to avoid modifying the original
        profile_data = data.copy()
        
        # List all expected profile fields for tracking
        expected_fields = ["bio", "skills", "experience", "interests", "name", "location", "projects"]
        logging.info(f"In-memory profile update with fields: {list(profile_data.keys())}")
        
        # Convert empty strings to None
        for key, value in profile_data.items():
            if isinstance(value, str) and value.strip() == '':
                profile_data[key] = None
                logging.info(f"Converting empty string to NULL for field: {key}")
        
        # Log the current in-memory profile state before updates
        logging.info(f"Current in-memory profile before update: {in_memory_profile}")
        
        # Update in-memory profile with new values
        for key, value in profile_data.items():
            if key != 'id' and key != 'project_list' and key != 'is_default':
                # Store the previous value for comparison
                previous_value = in_memory_profile.get(key, None)
                # Allow explicit NULL updates
                in_memory_profile[key] = value
                logging.info(f"Updated in-memory field '{key}': {previous_value} → {value}")
        
        # Add user_id if provided
        if user_id:
            in_memory_profile['user_id'] = user_id
            
        # Update timestamp
        in_memory_profile['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        
        # Save to file for persistence
        save_profile_to_file()
        logging.info("Saved updated profile to file")
        
        # Log the final in-memory profile state after updates
        logging.info(f"Final in-memory profile after update: {in_memory_profile}")
        
        # Return a copy of the updated profile
        updated_profile = in_memory_profile.copy()
        if user_id:
            updated_profile['user_id'] = user_id
        updated_profile['is_default'] = False
        
        # Add the project list if it exists
        if 'project_list' in in_memory_profile:
            updated_profile['project_list'] = in_memory_profile['project_list']
        else:
            updated_profile['project_list'] = []
        
        # Log what's being returned
        logging.info(f"Returning updated profile with fields: {list(updated_profile.keys())}")
        for field in expected_fields:
            if field in updated_profile:
                logging.info(f"Return field '{field}': {updated_profile[field]}")
            else:
                logging.info(f"Field '{field}' not present in returned profile")
        
        return {"success": True, "profile": updated_profile, "message": "Profile updated successfully (in-memory only)"}
    except Exception as e:
        logging.error(f"Error updating in-memory profile: {e}", exc_info=True)
        return {"success": False, "profile": None, "message": f"Error updating profile: {str(e)}"} 