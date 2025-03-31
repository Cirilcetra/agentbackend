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

def create_user_if_not_exists(user_id, username=None):
    """Create a user if it doesn't exist"""
    try:
        # Check if user exists
        user_response = supabase.table("users").select("id").eq("id", user_id).execute()
        
        if user_response.data and len(user_response.data) > 0:
            logger.info(f"User already exists: {user_id}")
            return True
        
        # Create user
        username = username or f"user_{user_id[:8]}"
        user_data = {
            "id": user_id,
            "username": username,
            "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        logger.info(f"Creating new user: {user_id}")
        user_response = supabase.table("users").insert(user_data).execute()
        
        if user_response.data and len(user_response.data) > 0:
            logger.info(f"User created successfully: {user_response.data[0]}")
            return True
        else:
            logger.error(f"Failed to create user: {user_response}")
            return False
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return False

def create_profile(user_id, name, bio, skills, experience, interests, location=None):
    """Create a new profile for a user"""
    try:
        # First ensure user exists
        if not create_user_if_not_exists(user_id):
            logger.error("Cannot create profile: Failed to ensure user exists")
            return False
        
        # Check if profile already exists
        profile_response = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
        
        if profile_response.data and len(profile_response.data) > 0:
            logger.info(f"Profile already exists for user: {user_id}. Will update it.")
            profile_id = profile_response.data[0]["id"]
            
            # Update existing profile
            profile_data = {
                "name": name,
                "bio": bio,
                "skills": skills,
                "experience": experience,
                "interests": interests,
                "projects": "[]",
                "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
            
            # Add location if provided
            if location:
                profile_data["location"] = location
            
            logger.info(f"Updating profile for user: {user_id}")
            update_response = supabase.table("profiles").update(profile_data).eq("id", profile_id).execute()
            
            if update_response.data and len(update_response.data) > 0:
                logger.info(f"Profile updated successfully: {update_response.data[0]}")
                return True
            else:
                logger.error(f"Failed to update profile: {update_response}")
                return False
        
        # Create new profile
        profile_data = {
            "user_id": user_id,
            "name": name,
            "bio": bio,
            "skills": skills,
            "experience": experience,
            "interests": interests,
            "projects": "[]",
            "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        # Add location if provided
        if location:
            profile_data["location"] = location
        
        logger.info(f"Creating new profile for user: {user_id}")
        profile_response = supabase.table("profiles").insert(profile_data).execute()
        
        if profile_response.data and len(profile_response.data) > 0:
            logger.info(f"Profile created successfully: {profile_response.data[0]}")
            return True
        else:
            logger.error(f"Failed to create profile: {profile_response}")
            return False
    except Exception as e:
        logger.error(f"Error creating profile: {e}")
        return False

def main():
    # Define example profile data
    user_id = "a1b1b837-5bcc-4d03-beff-87ed27d5941e"  # Default user ID
    name = "John Doe"
    bio = "Software engineer with expertise in AI and web development."
    skills = "Python, JavaScript, React, FastAPI, Machine Learning"
    experience = "5+ years in software development, specializing in AI applications."
    interests = "AI, machine learning, web development, reading"
    location = "San Francisco, CA"
    
    # Create profile
    success = create_profile(
        user_id=user_id,
        name=name,
        bio=bio,
        skills=skills,
        experience=experience,
        interests=interests,
        location=location
    )
    
    if success:
        print(f"Profile created/updated successfully for user: {user_id}")
    else:
        print(f"Failed to create/update profile for user: {user_id}")

if __name__ == "__main__":
    main() 