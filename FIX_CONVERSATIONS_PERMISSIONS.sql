-- Fix permissions for conversations table
-- This SQL adds the necessary RLS policies to allow proper access to the conversations table

-- First check if RLS is enabled
DO $$
BEGIN
    RAISE NOTICE 'Checking RLS status for conversations table...';
END $$;

-- Make sure RLS is enabled for the conversations table
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

-- Drop existing policies (if any) before creating new ones to avoid conflicts
DROP POLICY IF EXISTS "Chatbot owners can manage conversations" ON conversations;
DROP POLICY IF EXISTS "Service role can manage conversations" ON conversations;
DROP POLICY IF EXISTS "Authenticated users can view their conversations" ON conversations;

-- Create policies for the conversations table
-- Allow chatbot owners to view/update/delete their conversations
CREATE POLICY "Chatbot owners can manage conversations" ON conversations
  FOR ALL -- SELECT, INSERT, UPDATE, DELETE
  USING (auth.uid() = user_id) -- Checks apply to existing rows (SELECT, UPDATE, DELETE)
  WITH CHECK (auth.uid() = user_id); -- Checks apply to new/updated rows (INSERT, UPDATE)

-- Allow service_role full access (important for backend operations)
-- Using auth.role() instead of current_setting('role') as it's more reliable in Supabase
CREATE POLICY "Service role can manage conversations" ON conversations
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- Allow authenticated users to view conversations where they are the user_id
CREATE POLICY "Authenticated users can view their conversations" ON conversations
  FOR SELECT
  USING (auth.uid() = user_id);

-- Enable RLS for the messages table to ensure consistent permissions
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Drop all existing message policies to avoid conflicts
-- These include policies from previous versions and alternative naming patterns
DROP POLICY IF EXISTS "Users can view messages in their conversations" ON messages;
DROP POLICY IF EXISTS "Users can update messages in their conversations" ON messages;
DROP POLICY IF EXISTS "Users can delete messages in their conversations" ON messages;
DROP POLICY IF EXISTS "Service role can manage messages" ON messages;
DROP POLICY IF EXISTS "Anyone can insert messages" ON messages;
DROP POLICY IF EXISTS "Users can view messages for their chatbots" ON messages;
DROP POLICY IF EXISTS "Service role access to messages" ON messages;
DROP POLICY IF EXISTS "Users can insert messages" ON messages;
DROP POLICY IF EXISTS "Allow anonymous users to insert messages" ON messages;
DROP POLICY IF EXISTS "Allow anonymous read access to messages" ON messages;
DROP POLICY IF EXISTS "Chatbot owners can update message read status" ON messages;

-- Allow users to view messages in their conversations
CREATE POLICY "Users can view messages in their conversations" ON messages
  FOR SELECT 
  USING (
    EXISTS (
      SELECT 1 FROM conversations c 
      WHERE c.id = messages.conversation_id AND c.user_id = auth.uid()
    )
  );

-- Allow users to update messages in their conversations
CREATE POLICY "Users can update messages in their conversations" ON messages
  FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM conversations c 
      WHERE c.id = messages.conversation_id AND c.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM conversations c 
      WHERE c.id = messages.conversation_id AND c.user_id = auth.uid()
    )
  );

-- Allow users to delete messages in their conversations
CREATE POLICY "Users can delete messages in their conversations" ON messages
  FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM conversations c 
      WHERE c.id = messages.conversation_id AND c.user_id = auth.uid()
    )
  );

-- Allow service_role full access to messages
CREATE POLICY "Service role can manage messages" ON messages
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- Allow insert for anyone (the application will handle authorization)
CREATE POLICY "Anyone can insert messages" ON messages
  FOR INSERT
  WITH CHECK (true);

-- Grant necessary table permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON conversations TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON conversations TO service_role;
GRANT SELECT ON conversations TO anon;

-- Output success message
DO $$
BEGIN
    RAISE NOTICE 'Successfully applied RLS policies for conversations and messages tables';
END $$; 