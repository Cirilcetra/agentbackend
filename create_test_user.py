#!/usr/bin/env python3
import os
import time
import json
import logging
from dotenv import load_dotenv
from supabase import create_client

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
    exit(1)

# Initialize Supabase client
try:
    logger.info(f"Initializing Supabase client with URL: {SUPABASE_URL[:20]}...")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase client initialized")
except Exception as e:
    logger.error(f"Error initializing Supabase client: {e}")
    exit(1)

# Test user ID
TEST_USER_ID = "a1b1b837-5bcc-4d03-beff-87ed27d5941e"

def create_test_user():
    """Create a test user in the database"""
    try:
        # Check if user already exists
        user_response = supabase.table("users").select("id").eq("id", TEST_USER_ID).execute()
        
        if user_response.data and len(user_response.data) > 0:
            logger.info(f"User {TEST_USER_ID} already exists")
            return user_response.data[0]
        
        # Create user
        user_data = {
            "id": TEST_USER_ID,
            "username": "test_user",
            "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        user_response = supabase.table("users").insert(user_data).execute()
        
        if user_response.data and len(user_response.data) > 0:
            logger.info(f"Created user: {user_response.data[0]}")
            return user_response.data[0]
        else:
            logger.error(f"Failed to create user: {user_response}")
            return None
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return None

def create_test_profile():
    """Create a test profile for the user"""
    try:
        # Check if profile already exists
        profile_response = supabase.table("profiles").select("*").eq("user_id", TEST_USER_ID).execute()
        
        if profile_response.data and len(profile_response.data) > 0:
            logger.info(f"Profile for user {TEST_USER_ID} already exists")
            return profile_response.data[0]
        
        # Create profile
        profile_data = {
            "user_id": TEST_USER_ID,
            "name": "John Doe",
            "bio": "I am John, a software engineer with a passion for AI and web development.",
            "skills": "Python, JavaScript, React, Machine Learning",
            "experience": "5+ years in software development",
            "interests": "AI, web development, hiking",
            "location": "San Francisco, CA",
            "projects": "[]",
            "project_list": [],
            "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        profile_response = supabase.table("profiles").insert(profile_data).execute()
        
        if profile_response.data and len(profile_response.data) > 0:
            logger.info(f"Created profile: {profile_response.data[0]}")
            return profile_response.data[0]
        else:
            logger.error(f"Failed to create profile: {profile_response}")
            return None
    except Exception as e:
        logger.error(f"Error creating profile: {e}")
        return None

def create_test_chatbot():
    """Create a test chatbot for the user"""
    try:
        # Check if chatbot already exists
        chatbot_response = supabase.table("chatbots").select("*").eq("user_id", TEST_USER_ID).execute()
        
        if chatbot_response.data and len(chatbot_response.data) > 0:
            logger.info(f"Chatbot for user {TEST_USER_ID} already exists")
            return chatbot_response.data[0]
        
        # Create chatbot
        chatbot_data = {
            "user_id": TEST_USER_ID,
            "name": "John's Assistant",
            "description": "A helpful AI assistant for John",
            "is_public": True,
            "public_url_slug": f"john-{TEST_USER_ID[:8]}",
            "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        chatbot_response = supabase.table("chatbots").insert(chatbot_data).execute()
        
        if chatbot_response.data and len(chatbot_response.data) > 0:
            logger.info(f"Created chatbot: {chatbot_response.data[0]}")
            return chatbot_response.data[0]
        else:
            logger.error(f"Failed to create chatbot: {chatbot_response}")
            return None
    except Exception as e:
        logger.error(f"Error creating chatbot: {e}")
        return None

def main():
    """Create test user, profile, and chatbot"""
    # Create user
    user = create_test_user()
    if not user:
        logger.error("Failed to create test user")
        return
    
    # Create profile
    profile = create_test_profile()
    if not profile:
        logger.error("Failed to create test profile")
        return
    
    # Create chatbot
    chatbot = create_test_chatbot()
    if not chatbot:
        logger.error("Failed to create test chatbot")
        return
    
    logger.info("Successfully created test user, profile, and chatbot")
    logger.info(f"Test User ID: {TEST_USER_ID}")
    if chatbot:
        logger.info(f"Test Chatbot ID: {chatbot.get('id')}")
        logger.info(f"Test Chatbot Name: {chatbot.get('name')}")

if __name__ == "__main__":
    main() 