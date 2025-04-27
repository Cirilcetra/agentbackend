-- First, modify the file_path constraint to allow NULL values temporarily
ALTER TABLE user_documents ALTER COLUMN file_path DROP NOT NULL;

-- Update any NULL file_path values with the storage_path if available
UPDATE user_documents
SET file_path = storage_path
WHERE file_path IS NULL AND storage_path IS NOT NULL;

-- Set a default value for any remaining NULL file_path entries
UPDATE user_documents
SET file_path = CONCAT('default_path/', id)
WHERE file_path IS NULL;

-- Restructure the user_documents table to match your application needs
ALTER TABLE user_documents
ADD COLUMN IF NOT EXISTS description TEXT,
ADD COLUMN IF NOT EXISTS extracted_text TEXT,
ADD COLUMN IF NOT EXISTS mime_type TEXT,
ADD COLUMN IF NOT EXISTS storage_path TEXT;

-- Create an index on user_id for better performance
CREATE INDEX IF NOT EXISTS idx_user_documents_user_id ON user_documents(user_id);

-- If you decide to keep the NOT NULL constraint on file_path after fixes:
-- ALTER TABLE user_documents ALTER COLUMN file_path SET NOT NULL;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON TABLE user_documents TO authenticated;
GRANT ALL PRIVILEGES ON TABLE user_documents TO service_role;

-- Drop the existing view
DROP VIEW IF EXISTS messages_with_visitors;

-- Create a new view without the direct auth.uid() reference
CREATE VIEW messages_with_visitors AS
SELECT 
    m.id,
    m.chatbot_id,
    m.visitor_id,
    m.visitor_id_text,
    m.message,
    m.response,
    m.sender,
    m.timestamp,
    m.target_user_id,
    m.metadata,
    m.created_at,
    m.is_read,
    v.visitor_id AS visitor_identifier,
    v.name AS visitor_name,
    v.email AS visitor_email,
    c.user_id AS chatbot_owner_id,
    c.name AS chatbot_name
FROM 
    messages m
LEFT JOIN 
    visitors v ON m.visitor_id = v.id
LEFT JOIN 
    chatbots c ON m.chatbot_id = c.id;

-- Grant broad permissions (we'll rely on the underlying table's RLS)
GRANT SELECT ON messages_with_visitors TO authenticated;
GRANT SELECT ON messages_with_visitors TO service_role;
GRANT SELECT ON messages_with_visitors TO anon;

-- Ensure the underlying messages table has proper RLS
-- First, remove any overly permissive policies
DROP POLICY IF EXISTS "Backend service full access to messages" ON messages;

-- Make sure the service_role can access messages
DROP POLICY IF EXISTS "Service role access to messages" ON messages;
CREATE POLICY "Service role access to messages" ON messages
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- Make sure authenticated users can only see their messages
DROP POLICY IF EXISTS "Users can view messages for their chatbots" ON messages;
CREATE POLICY "Users can view messages for their chatbots" ON messages
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM chatbots
      WHERE chatbots.id = messages.chatbot_id 
      AND chatbots.user_id = auth.uid()
    )
  );