#!/usr/bin/env python3
import json
import os
import sys
import time
from dotenv import load_dotenv
from supabase import create_client, Client
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('fix_profile_fields.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

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

def load_backup_profile():
    """Load the profile backup file"""
    try:
        if os.path.exists('profile_backup.json'):
            with open('profile_backup.json', 'r') as f:
                profile_data = json.load(f)
                logger.info(f"Loaded profile from backup file with name: {profile_data.get('name', 'unknown')}")
                return profile_data
        else:
            logger.error("Profile backup file not found")
            return None
    except Exception as e:
        logger.error(f"Error loading profile backup: {e}")
        return None

def update_all_profiles():
    """Update all profiles with proper name and location"""
    try:
        # Load backup profile
        backup_profile = load_backup_profile()
        if not backup_profile:
            logger.error("No backup profile available, cannot proceed")
            return False
        
        # Get name and location from backup
        name = backup_profile.get("name")
        location = backup_profile.get("location")
        
        if not name or not location:
            logger.error(f"Missing name or location in backup profile. Name: {name}, Location: {location}")
            return False
        
        logger.info(f"Using name '{name}' and location '{location}' from backup profile")
        
        # Get all profiles from database
        profiles_response = supabase.table("profiles").select("*").execute()
        
        if not profiles_response.data:
            logger.warning("No profiles found in database")
            return False
        
        logger.info(f"Found {len(profiles_response.data)} profiles to update")
        
        # Update each profile
        updated_count = 0
        for profile in profiles_response.data:
            profile_id = profile["id"]
            user_id = profile["user_id"]
            current_name = profile.get("name")
            current_location = profile.get("location")
            
            # Only update if name or location is missing
            if current_name is None or current_location is None:
                update_data = {}
                
                if current_name is None:
                    update_data["name"] = name
                
                if current_location is None:
                    update_data["location"] = location
                
                if update_data:
                    logger.info(f"Updating profile {profile_id} for user {user_id} with {update_data}")
                    try:
                        update_response = supabase.table("profiles").update(update_data).eq("id", profile_id).execute()
                        if update_response.data:
                            logger.info(f"Successfully updated profile {profile_id}")
                            updated_count += 1
                        else:
                            logger.error(f"Failed to update profile {profile_id}: {update_response}")
                    except Exception as update_error:
                        logger.error(f"Error updating profile {profile_id}: {update_error}")
        
        logger.info(f"Updated {updated_count} profiles out of {len(profiles_response.data)}")
        return True
    except Exception as e:
        logger.error(f"Error updating profiles: {e}")
        return False

def main():
    logger.info("Starting profile fields fix")
    
    success = update_all_profiles()
    
    if success:
        logger.info("Profile fields fix completed successfully")
    else:
        logger.error("Profile fields fix failed")

if __name__ == "__main__":
    main() 