#!/usr/bin/env python3
import requests
import json
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the environment variables
PORT = os.getenv("PORT", "8080")
HOST = os.getenv("HOST", "0.0.0.0")
API_URL = os.getenv("API_URL", f"http://localhost:{PORT}")
TEST_USER_ID = os.getenv("TEST_USER_ID", "754093fa-dca3-4ec8-892c-b278e3207dc1")  # Using the test user ID

def test_profile_update():
    """Test updating a profile with a specific field"""
    
    # Define the profile update data
    profile_data = {
        "bio": "This is a test bio from automated test - " + time.strftime('%Y-%m-%d %H:%M:%S'),
        "skills": "Test skills from automated test",
        "experience": "Test experience from automated test",
        "interests": "Test interests from automated test"
    }
    
    print(f"Updating profile with test data: {profile_data}")
    print(f"Sending request to: {API_URL}/profile?user_id={TEST_USER_ID}")
    
    try:
        # Make the request to update the profile
        response = requests.post(
            f"{API_URL}/profile?user_id={TEST_USER_ID}",
            json=profile_data,
            timeout=10  # Add timeout to avoid hanging
        )
        
        # Check the response
        if response.status_code == 200:
            result = response.json()
            print("Profile update successful!")
            print(f"Response: {json.dumps(result, indent=2)}")
            
            # Verify updated fields
            if "profile" in result:
                profile = result["profile"]
                for key, value in profile_data.items():
                    if key in profile:
                        print(f"Checking field '{key}':")
                        print(f"  Expected: {value}")
                        print(f"  Actual: {profile[key]}")
                        if profile[key] == value:
                            print("  ✅ Match")
                        else:
                            print("  ❌ Mismatch")
                    else:
                        print(f"❌ Field '{key}' missing from response")
        else:
            print(f"Error: HTTP {response.status_code}")
            print(response.text)
    except requests.exceptions.ConnectionError as ce:
        print(f"Connection error: {ce}")
        print("Is the server running? Make sure the API is accessible at:", API_URL)
    except Exception as e:
        print(f"Error during request: {e}")

def test_empty_profile_update():
    """Test updating a profile with empty fields to check if they're properly nullified"""
    
    # Define the profile update data with empty fields
    profile_data = {
        "bio": "",  # Empty string should be converted to NULL
        "skills": "   ",  # Whitespace string should be converted to NULL
        "experience": "This field should persist",
        "interests": ""
    }
    
    print(f"Updating profile with empty fields: {profile_data}")
    print(f"Sending request to: {API_URL}/profile?user_id={TEST_USER_ID}")
    
    try:
        # Make the request to update the profile
        response = requests.post(
            f"{API_URL}/profile?user_id={TEST_USER_ID}",
            json=profile_data,
            timeout=10  # Add timeout to avoid hanging
        )
        
        # Check the response
        if response.status_code == 200:
            result = response.json()
            print("Empty fields update successful!")
            print(f"Response: {json.dumps(result, indent=2)}")
            
            # Verify fields are properly handled
            if "profile" in result:
                profile = result["profile"]
                for key, value in profile_data.items():
                    if key in profile:
                        print(f"Checking field '{key}':")
                        print(f"  Input: '{value}'")
                        print(f"  Response: '{profile[key]}'")
                        
                        # Empty strings should be converted to None/null
                        if value.strip() == "" and profile[key] is None:
                            print("  ✅ Empty string correctly converted to null")
                        elif value.strip() != "" and profile[key] == value:
                            print("  ✅ Non-empty value preserved correctly")
                        else:
                            print("  ❌ Field not handled correctly")
                    else:
                        print(f"❌ Field '{key}' missing from response")
        else:
            print(f"Error: HTTP {response.status_code}")
            print(response.text)
    except requests.exceptions.ConnectionError as ce:
        print(f"Connection error: {ce}")
        print("Is the server running? Make sure the API is accessible at:", API_URL)
    except Exception as e:
        print(f"Error during request: {e}")

def get_profile():
    """Get the current profile"""
    
    print(f"Getting profile from: {API_URL}/profile?user_id={TEST_USER_ID}")
    
    try:
        response = requests.get(
            f"{API_URL}/profile?user_id={TEST_USER_ID}",
            timeout=10  # Add timeout to avoid hanging
        )
        
        if response.status_code == 200:
            profile = response.json()
            print("Current profile:")
            print(json.dumps(profile, indent=2))
        else:
            print(f"Error: HTTP {response.status_code}")
            print(response.text)
    except requests.exceptions.ConnectionError as ce:
        print(f"Connection error: {ce}")
        print("Is the server running? Make sure the API is accessible at:", API_URL)
    except Exception as e:
        print(f"Error during request: {e}")

if __name__ == "__main__":
    print(f"Testing against API at: {API_URL}")
    print(f"Using test user ID: {TEST_USER_ID}")
    
    # Menu system
    while True:
        print("\n--- Profile Update Test Menu ---")
        print("1. Get current profile")
        print("2. Run standard profile update test")
        print("3. Run empty fields test")
        print("4. Exit")
        
        choice = input("Enter your choice (1-4): ")
        
        if choice == "1":
            get_profile()
        elif choice == "2":
            test_profile_update()
        elif choice == "3":
            test_empty_profile_update()
        elif choice == "4":
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.") 