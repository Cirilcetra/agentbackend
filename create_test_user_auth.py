#!/usr/bin/env python3
import os
import time
import json
import logging
import uuid
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

# Email and password for the test user
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "TestPassword123!"

def sign_up_test_user():
    """Sign up a test user through Supabase Auth"""
    try:
        # Try to sign up a new user
        response = supabase.auth.sign_up({
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if response.user:
            user_id = response.user.id
            logger.info(f"Successfully signed up user: {user_id}")
            return user_id
        else:
            logger.error(f"Failed to sign up user: {response}")
            return None
    except Exception as e:
        logger.error(f"Error signing up user: {e}")
        
        # If user already exists, try to sign in
        try:
            logger.info("Attempting to sign in with existing credentials...")
            response = supabase.auth.sign_in_with_password({
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            
            if response.user:
                user_id = response.user.id
                logger.info(f"Successfully signed in as existing user: {user_id}")
                return user_id
            else:
                logger.error(f"Failed to sign in: {response}")
                return None
        except Exception as sign_in_error:
            logger.error(f"Error signing in: {sign_in_error}")
            return None

def create_test_profile(user_id):
    """Create a test profile for the user"""
    try:
        # Check if profile already exists
        profile_response = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
        
        if profile_response.data and len(profile_response.data) > 0:
            logger.info(f"Profile for user {user_id} already exists")
            return profile_response.data[0]
        
        # Create profile
        profile_data = {
            "user_id": user_id,
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

def create_test_chatbot(user_id):
    """Create a test chatbot for the user"""
    try:
        # Check if chatbot already exists
        chatbot_response = supabase.table("chatbots").select("*").eq("user_id", user_id).execute()
        
        if chatbot_response.data and len(chatbot_response.data) > 0:
            logger.info(f"Chatbot for user {user_id} already exists")
            return chatbot_response.data[0]
        
        # Create chatbot
        chatbot_data = {
            "user_id": user_id,
            "name": "John's Assistant",
            "description": "A helpful AI assistant for John",
            "is_public": True,
            "public_url_slug": f"john-{str(uuid.uuid4())[:8]}",
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
    # Sign up or sign in test user
    user_id = sign_up_test_user()
    if not user_id:
        logger.error("Failed to create or sign in test user")
        return
    
    # Create profile
    profile = create_test_profile(user_id)
    if not profile:
        logger.error("Failed to create test profile")
        return
    
    # Create chatbot
    chatbot = create_test_chatbot(user_id)
    if not chatbot:
        logger.error("Failed to create test chatbot")
        return
    
    logger.info("Successfully created test user, profile, and chatbot")
    logger.info(f"Test User ID: {user_id}")
    logger.info(f"Test User Email: {TEST_EMAIL}")
    if chatbot:
        logger.info(f"Test Chatbot ID: {chatbot.get('id')}")
        logger.info(f"Test Chatbot Name: {chatbot.get('name')}")
        logger.info(f"Public URL: {chatbot.get('public_url_slug')}")

if __name__ == "__main__":
    main() 