-- EMERGENCY FIX: This is a temporary solution to allow unauthenticated access
-- WARNING: This disables security features for testing purposes
-- Re-enable RLS policies before going to production

-- 1. Add required columns to messages
ALTER TABLE messages ADD COLUMN IF NOT EXISTS visitor_id_text TEXT;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE messages ADD COLUMN IF NOT EXISTS target_user_id UUID;

-- 2. Make chatbot_id column nullable (critical fix)
ALTER TABLE messages ALTER COLUMN chatbot_id DROP NOT NULL;

-- 3. DISABLE ROW LEVEL SECURITY COMPLETELY for testing
ALTER TABLE messages DISABLE ROW LEVEL SECURITY;
ALTER TABLE visitors DISABLE ROW LEVEL SECURITY; 
ALTER TABLE chatbots DISABLE ROW LEVEL SECURITY;
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE profiles DISABLE ROW LEVEL SECURITY;

-- 4. Grant ALL permissions to anonymous users (highly permissive but will work)
GRANT ALL ON messages TO anon;
GRANT ALL ON visitors TO anon;
GRANT ALL ON chatbots TO anon;
GRANT USAGE ON SCHEMA public TO anon;

-- 5. Force cache refresh
NOTIFY pgrst, 'reload config';

-- 6. Create a default chatbot if none exists
DO $$
DECLARE
  default_user_id UUID;
BEGIN
  -- Get first user or create a dummy one
  SELECT id INTO default_user_id FROM users LIMIT 1;
  
  IF default_user_id IS NULL THEN
    -- Create a dummy user if no users exist
    INSERT INTO users (id, username, created_at, updated_at)
    VALUES (
      uuid_generate_v4(), 
      'default_user', 
      NOW(), 
      NOW()
    )
    RETURNING id INTO default_user_id;
  END IF;
  
  -- Create a default chatbot if none exists
  IF NOT EXISTS (SELECT 1 FROM chatbots LIMIT 1) THEN
    INSERT INTO chatbots (
      id,
      user_id,
      name,
      description,
      is_public,
      public_url_slug,
      created_at,
      updated_at
    )
    VALUES (
      uuid_generate_v4(),
      default_user_id,
      'Default Chatbot',
      'Default chatbot for the system',
      true,
      'default',
      NOW(),
      NOW()
    );
  END IF;
END
$$;

-- EMERGENCY FIX: Add project_list column to profiles table
-- Use this if you only need the column and don't need the trigger functionality

-- Add project_list column as JSONB
ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS project_list JSONB DEFAULT '[]'::jsonb;

-- Copy data from projects (text) to project_list (jsonb) for existing rows
UPDATE profiles
SET project_list = CASE 
                     WHEN projects IS NULL THEN '[]'::jsonb
                     WHEN projects = '' THEN '[]'::jsonb
                     ELSE projects::jsonb
                   END
WHERE project_list IS NULL OR project_list = '[]'::jsonb; 