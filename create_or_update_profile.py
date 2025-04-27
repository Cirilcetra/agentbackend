#!/usr/bin/env python3
import json
import os
import sys
import time
from dotenv import load_dotenv
from supabase import create_client, Client
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Load DEFAULT_PROFILE from the application
DEFAULT_PROFILE = {
    "name": "John Doe",  # Proper default name 
    "bio": "Software engineer with expertise in AI and web development.",
    "skills": "Python, JavaScript, React, FastAPI, Machine Learning",
    "experience": "5+ years in software development, specializing in AI applications.",
    "interests": "AI, machine learning, web development, reading",
    "project_list": []
}

# Get Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Missing Supabase credentials. Please set SUPABASE_URL and SUPABASE_KEY in .env file.")
    sys.exit(1)

# Initialize Supabase client
try:
    logger.info(f"Initializing Supabase client with URL: {SUPABASE_URL[:20]}...")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase client initialized")
except Exception as e:
    logger.error(f"Error initializing Supabase client: {e}")
    sys.exit(1)

def update_or_create_in_memory_profile(name):
    """Update the in-memory profile with the correct name and save it to file"""
    try:
        # Create new profile data
        profile_data = DEFAULT_PROFILE.copy()
        profile_data["name"] = name
        profile_data["updated_at"] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        
        # Save to file
        with open('backend/profile_backup.json', 'w') as f:
            json.dump(profile_data, f, indent=2)
        
        logger.info(f"Updated in-memory profile with name: {name}")
        logger.info(f"Saved to profile_backup.json")
        return True
    except Exception as e:
        logger.error(f"Error updating in-memory profile: {e}")
        return False

def update_profile_in_supabase(user_id, name):
    """Try to update the profile in Supabase"""
    try:
        # First check if profile exists
        profile_response = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
        
        if profile_response.data and len(profile_response.data) > 0:
            # Update existing profile
            profile_id = profile_response.data[0]["id"]
            logger.info(f"Found profile with ID: {profile_id}")
            
            # Update only the name
            update_response = supabase.table("profiles").update({"name": name}).eq("id", profile_id).execute()
            
            if update_response.data and len(update_response.data) > 0:
                logger.info(f"Profile name updated successfully: {update_response.data[0].get('name')}")
                return True
            else:
                logger.error(f"Failed to update profile name: {update_response}")
                return False
        else:
            logger.warning(f"No profile found for user_id: {user_id}")
            logger.warning("Will only update the local profile backup file")
            return False
    except Exception as e:
        logger.error(f"Error updating profile in Supabase: {e}")
        return False

def main():
    # Get name from command line or use default
    name = "John Doe"  # Default name
    user_id = "a1b1b837-5bcc-4d03-beff-87ed27d5941e"  # Default user ID
    
    # Override from command line if provided
    if len(sys.argv) > 1:
        name = sys.argv[1]
    if len(sys.argv) > 2:
        user_id = sys.argv[2]
    
    # Try to update in Supabase
    supabase_success = update_profile_in_supabase(user_id, name)
    
    # Update in-memory profile
    file_success = update_or_create_in_memory_profile(name)
    
    if supabase_success:
        print(f"Successfully updated profile name to '{name}' in Supabase")
    else:
        print(f"Failed to update profile in Supabase - check logs for details")
    
    if file_success:
        print(f"Successfully updated local profile backup file with name '{name}'")
    else:
        print(f"Failed to update local profile backup file")
    
    # Overall success
    print("\nSummary:")
    if supabase_success or file_success:
        print("Operation partially or fully successful!")
        print("Please restart your backend server to see the changes")
    else:
        print("Operation failed completely. Check logs for details.")

if __name__ == "__main__":
    main() 