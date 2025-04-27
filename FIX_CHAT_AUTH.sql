-- Comprehensive fix for chat authentication issues

-- 1. Fix any missing columns in the messages table
ALTER TABLE messages ADD COLUMN IF NOT EXISTS visitor_id_text TEXT;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE messages ADD COLUMN IF NOT EXISTS target_user_id UUID;

-- 2. Create indexes on important columns
CREATE INDEX IF NOT EXISTS idx_messages_visitor_id_text ON messages(visitor_id_text);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);

-- 3. Make sure Row Level Security is enabled
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE visitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE chatbots ENABLE ROW LEVEL SECURITY;

-- 4. VERY IMPORTANT: Temporarily disable Row Level Security for testing
-- Comment out the next 3 lines when you're ready for production
ALTER TABLE messages DISABLE ROW LEVEL SECURITY;
ALTER TABLE visitors DISABLE ROW LEVEL SECURITY;
ALTER TABLE chatbots DISABLE ROW LEVEL SECURITY;

-- 5. Grant permissions to anonymous users
GRANT USAGE ON SCHEMA public TO anon;
GRANT SELECT, INSERT ON messages TO anon;
GRANT SELECT, INSERT ON visitors TO anon;
GRANT SELECT ON chatbots TO anon;

-- 6. Create permissive policies for anonymous users
DROP POLICY IF EXISTS "Anyone can insert messages" ON messages;
CREATE POLICY "Anyone can insert messages" ON messages
  FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "Anyone can select messages" ON messages;
CREATE POLICY "Anyone can select messages" ON messages
  FOR SELECT USING (true);

DROP POLICY IF EXISTS "Anyone can insert visitors" ON visitors;
CREATE POLICY "Anyone can insert visitors" ON visitors
  FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "Anyone can select visitors" ON visitors;
CREATE POLICY "Anyone can select visitors" ON visitors
  FOR SELECT USING (true);

DROP POLICY IF EXISTS "Anyone can select public chatbots" ON chatbots;
CREATE POLICY "Anyone can select public chatbots" ON chatbots
  FOR SELECT USING (is_public = true);

-- 7. Ensure a default chatbot exists
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
  (SELECT id FROM users ORDER BY created_at LIMIT 1),
  'Default Chatbot',
  'A default chatbot for the system',
  true,
  'default-bot',
  NOW(),
  NOW()
WHERE 
  NOT EXISTS (SELECT 1 FROM chatbots LIMIT 1) AND
  EXISTS (SELECT 1 FROM users LIMIT 1);

-- 8. Create a function to get the default chatbot ID
CREATE OR REPLACE FUNCTION get_default_chatbot_id() 
RETURNS UUID AS $$
DECLARE
  default_id UUID;
BEGIN
  SELECT id INTO default_id FROM chatbots LIMIT 1;
  RETURN default_id;
END;
$$ LANGUAGE plpgsql;

-- 9. Create view to help troubleshoot visitor relationships
CREATE OR REPLACE VIEW visitor_summary AS
SELECT 
  v.id,
  v.visitor_id,
  v.name,
  v.first_seen,
  v.last_seen,
  COUNT(m.id) AS message_count
FROM 
  visitors v
LEFT JOIN
  messages m ON v.id = m.visitor_id
GROUP BY
  v.id, v.visitor_id, v.name, v.first_seen, v.last_seen;

-- 10. Update the function to handle null chatbot_id
CREATE OR REPLACE FUNCTION handle_missing_chatbot()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.chatbot_id IS NULL THEN
    NEW.chatbot_id := get_default_chatbot_id();
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 11. Create trigger to automatically add chatbot_id if missing
DROP TRIGGER IF EXISTS ensure_chatbot_id ON messages;
CREATE TRIGGER ensure_chatbot_id
  BEFORE INSERT ON messages
  FOR EACH ROW
  EXECUTE FUNCTION handle_missing_chatbot();

-- 12. Make column nullable for compatibility with old code
ALTER TABLE messages ALTER COLUMN chatbot_id DROP NOT NULL;

-- 13. Force refresh the policy cache
NOTIFY pgrst, 'reload config'; 