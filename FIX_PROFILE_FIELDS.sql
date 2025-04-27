-- FIX_PROFILE_FIELDS.sql
-- This script fixes the issue with name and location fields not being saved/displayed correctly

-- First, check if columns exist (they should, but let's be safe)
DO $$
BEGIN
    -- Check if name column exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'profiles' AND column_name = 'name'
    ) THEN
        -- Add name column if it doesn't exist
        ALTER TABLE profiles ADD COLUMN name TEXT;
    END IF;

    -- Check if location column exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'profiles' AND column_name = 'location'
    ) THEN
        -- Add location column if it doesn't exist
        ALTER TABLE profiles ADD COLUMN location TEXT;
    END IF;
END $$;

-- Display current state of profiles (name and location fields)
SELECT id, user_id, name, location FROM profiles;

-- Update profiles that have NULL name values with a default value
UPDATE profiles 
SET name = 'User ' || substring(user_id::text from 1 for 8) 
WHERE name IS NULL;

-- Update profiles that have NULL location values with default
UPDATE profiles
SET location = 'Unknown Location'
WHERE location IS NULL;

-- For profiles that have username from users table, update name from there if applicable
UPDATE profiles p
SET name = u.username
FROM users u
WHERE p.user_id = u.id
AND p.name = 'User ' || substring(p.user_id::text from 1 for 8)
AND u.username IS NOT NULL
AND u.username <> 'user_' || substring(u.id::text from 1 for 8);

-- Display updated state of profiles
SELECT id, user_id, name, location FROM profiles; 