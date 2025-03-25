#!/usr/bin/env python3
import json
import os
from app.database import in_memory_profile

def save_in_memory_profile():
    """Save the in-memory profile to a file for persistence"""
    try:
        with open('profile_backup.json', 'w') as f:
            json.dump(in_memory_profile, f, indent=2)
        print("In-memory profile saved to profile_backup.json")
    except Exception as e:
        print(f"Error saving in-memory profile: {e}")

def load_in_memory_profile():
    """Load the in-memory profile from a file"""
    try:
        if os.path.exists('profile_backup.json'):
            with open('profile_backup.json', 'r') as f:
                profile_data = json.load(f)
                in_memory_profile.update(profile_data)
                print("In-memory profile loaded from profile_backup.json")
                return True
        else:
            print("No profile backup file found")
            return False
    except Exception as e:
        print(f"Error loading in-memory profile: {e}")
        return False

if __name__ == "__main__":
    action = input("Enter 'save' to save profile or 'load' to load profile: ").strip().lower()
    
    if action == 'save':
        save_in_memory_profile()
    elif action == 'load':
        load_in_memory_profile()
    else:
        print("Invalid action. Please enter 'save' or 'load'.") 