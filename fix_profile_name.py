#!/usr/bin/env python3
import json
import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
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

def update_profile_name(user_id, new_name):
    """Update profile name for a specific user"""
    try:
        # Check if profile exists
        logger.info(f"Checking if profile exists for user_id: {user_id}")
        profile_response = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
        
        if not profile_response.data or len(profile_response.data) == 0:
            logger.error(f"No profile found for user_id: {user_id}")
            return False
        
        # Get profile ID
        profile_id = profile_response.data[0]["id"]
        logger.info(f"Found profile with ID: {profile_id}")
        
        # Update profile name
        logger.info(f"Updating profile name to: {new_name}")
        update_response = supabase.table("profiles").update({"name": new_name}).eq("id", profile_id).execute()
        
        if update_response.data and len(update_response.data) > 0:
            logger.info(f"Profile name updated successfully: {update_response.data[0]}")
            return True
        else:
            logger.error(f"Failed to update profile name: {update_response}")
            return False
    except Exception as e:
        logger.error(f"Error updating profile name: {e}")
        return False

def main():
    # Get command line arguments
    if len(sys.argv) < 3:
        print("Usage: python fix_profile_name.py <user_id> <new_name>")
        print("Example: python fix_profile_name.py a1b1b837-5bcc-4d03-beff-87ed27d5941e 'John Doe'")
        sys.exit(1)
    
    user_id = sys.argv[1]
    new_name = sys.argv[2]
    
    # Update profile name
    success = update_profile_name(user_id, new_name)
    
    if success:
        print(f"Profile name updated to '{new_name}' for user_id: {user_id}")
    else:
        print(f"Failed to update profile name for user_id: {user_id}")

if __name__ == "__main__":
    main() 