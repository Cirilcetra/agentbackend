#!/usr/bin/env python
"""
Test script to directly update a profile in Supabase.
This bypasses the API and tests the database connection directly.

Usage:
    python test_profile_update.py

Make sure you have the .env file configured with Supabase credentials.
"""
import os
import logging
from supabase import create_client
from dotenv import load_dotenv
import json
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Test user ID - replace with a real user ID from your database
TEST_USER_ID = "REPLACE_WITH_REAL_USER_ID"  

def test_profile_update():
    """Test updating a profile directly in Supabase"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        logging.error("Supabase credentials not found in environment variables.")
        return
        
    logging.info(f"Connecting to Supabase: {SUPABASE_URL}")
    
    try:
        # Create Supabase client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Test data - this is what we want to save
        test_data = {
            "bio": "Professional software engineer specializing in full-stack development.",
            "skills": "Python, JavaScript, TypeScript, React, FastAPI, SQL, NoSQL",
            "experience": "10+ years of experience in building scalable applications.",
            "interests": "Machine learning, cloud computing, open-source contribution"
        }
        
        # Add timestamp
        test_data['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        
        # First, get the current profile
        logging.info(f"Fetching current profile for user: {TEST_USER_ID}")
        response = supabase.table("profiles").select("*").eq("user_id", TEST_USER_ID).execute()
        
        if not response.data or len(response.data) == 0:
            logging.error(f"No profile found for user ID: {TEST_USER_ID}")
            return
            
        current_profile = response.data[0]
        logging.info(f"Current profile: {json.dumps(current_profile, indent=2)}")
        
        # Update the profile
        logging.info(f"Updating profile with data: {json.dumps(test_data, indent=2)}")
        update_response = supabase.table("profiles").update(test_data).eq("user_id", TEST_USER_ID).execute()
        
        if not update_response.data or len(update_response.data) == 0:
            logging.error("Failed to update profile. Response: %s", update_response)
            return
            
        updated_profile = update_response.data[0]
        logging.info(f"Profile updated successfully. Updated profile: {json.dumps(updated_profile, indent=2)}")
        
        # Verify the update by fetching the profile again
        verify_response = supabase.table("profiles").select("*").eq("user_id", TEST_USER_ID).execute()
        if verify_response.data and len(verify_response.data) > 0:
            verified_profile = verify_response.data[0]
            logging.info(f"Verified profile: {json.dumps(verified_profile, indent=2)}")
            
            # Check if fields were updated correctly
            success = True
            for key, value in test_data.items():
                if key == 'updated_at':
                    continue
                if verified_profile.get(key) != value:
                    logging.error(f"Field {key} was not updated correctly. Expected: {value}, Got: {verified_profile.get(key)}")
                    success = False
            
            if success:
                logging.info("All fields were updated correctly!")
            
    except Exception as e:
        logging.exception(f"Error testing profile update: {e}")

if __name__ == "__main__":
    test_profile_update() 