-- Fix anonymous access for chat functionality

-- Make sure RLS is enabled on all important tables
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE visitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE chatbots ENABLE ROW LEVEL SECURITY;

-- Grant necessary permissions to anonymous users
GRANT SELECT, INSERT ON messages TO anon;
GRANT SELECT, INSERT ON visitors TO anon;
GRANT SELECT ON chatbots TO anon;

-- Fix for missing visitor_id_text column if it doesn't exist
ALTER TABLE messages ADD COLUMN IF NOT EXISTS visitor_id_text TEXT;

-- Drop existing policies that might be restricting access
DROP POLICY IF EXISTS "Anyone can insert messages" ON messages;
DROP POLICY IF EXISTS "Anyone can insert visitors" ON visitors;

-- Create permissive policies for anonymous users
CREATE POLICY "Anyone can insert messages" ON messages
  FOR INSERT WITH CHECK (true);

CREATE POLICY "Anyone can select messages" ON messages
  FOR SELECT USING (true);

CREATE POLICY "Anyone can insert visitors" ON visitors
  FOR INSERT WITH CHECK (true);

CREATE POLICY "Anyone can select visitors" ON visitors
  FOR SELECT USING (true);

CREATE POLICY "Anyone can select public chatbots" ON chatbots
  FOR SELECT USING (is_public = true);

-- Make sure the visitors table has the needed columns and permissions
ALTER TABLE visitors ALTER COLUMN visitor_id TYPE TEXT;

-- Ensure uuid extension is available
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Set updated CORS settings in auth.config if needed
UPDATE auth.config
SET enable_signup = true,
    site_url = '*',
    additional_redirect_urls = array_append(additional_redirect_urls, '*');

-- Force refresh policy cache
NOTIFY pgrst, 'reload config';

-- Optionally create a default chatbot if none exists
DO $$
BEGIN
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
    SELECT 
      uuid_generate_v4(),
      (SELECT id FROM users LIMIT 1),
      'Default Chatbot',
      'A default chatbot for testing',
      true,
      'default',
      NOW(),
      NOW()
    WHERE EXISTS (SELECT 1 FROM users LIMIT 1);
  END IF;
END
$$; 