-- Migration script to introduce a conversations table

BEGIN; -- Start transaction

-- 1. Create the conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chatbot_id UUID NOT NULL REFERENCES chatbots(id) ON DELETE CASCADE,
    visitor_id UUID REFERENCES visitors(id) ON DELETE SET NULL, -- Allow visitor deletion without losing conversation history associated with the chatbot owner
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- Store the chatbot owner's ID for easier RLS
    title TEXT, -- Optional: Could be auto-generated or set later
    status TEXT DEFAULT 'active', -- e.g., active, archived
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_message_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- Will be updated by trigger or application logic
    -- Ensure a unique conversation per chatbot/visitor pair
    UNIQUE (chatbot_id, visitor_id) 
);

COMMENT ON COLUMN conversations.user_id IS 'Stores the user_id of the owner of the chatbot referenced by chatbot_id. Used for RLS.';
COMMENT ON TABLE conversations IS 'Represents a chat conversation thread between a visitor and a chatbot.';


-- 2. Add conversation_id column to messages (initially nullable for migration)
ALTER TABLE messages
ADD COLUMN IF NOT EXISTS conversation_id UUID;

COMMENT ON COLUMN messages.conversation_id IS 'Links the message to a specific conversation thread.';


-- 3. Migrate existing messages to conversations
-- Create conversations based on distinct chatbot_id and visitor_id pairs in messages
-- and populate the user_id from the chatbot owner.
INSERT INTO conversations (chatbot_id, visitor_id, user_id, created_at, updated_at, last_message_at)
SELECT
    m.chatbot_id,
    m.visitor_id,
    c.user_id, -- Get the owner from the chatbot
    MIN(m.created_at) as conversation_created_at, -- Set conversation created_at to the first message time
    MAX(m.created_at) as conversation_updated_at, -- Set conversation updated_at to the last message time
    MAX(m.created_at) as conversation_last_message_at -- Set conversation last_message_at to the last message time
FROM
    messages m
JOIN
    chatbots c ON m.chatbot_id = c.id
WHERE 
    m.conversation_id IS NULL -- Only process messages not yet migrated (if script is re-run)
GROUP BY
    m.chatbot_id, m.visitor_id, c.user_id
ON CONFLICT (chatbot_id, visitor_id) DO NOTHING; -- Avoid errors if a conversation already exists for the pair

-- Update messages table to link messages to their corresponding conversation
UPDATE messages m
SET conversation_id = sub.conv_id
FROM (
    SELECT 
        con.id as conv_id, 
        con.chatbot_id as chat_id, 
        con.visitor_id as vis_id 
    FROM conversations con
) AS sub
WHERE 
    m.chatbot_id = sub.chat_id 
    AND m.visitor_id = sub.vis_id -- Match based on chatbot and visitor
    AND m.conversation_id IS NULL; -- Only update messages that haven't been linked yet


-- 4. Make conversation_id NOT NULL and add Foreign Key constraint
-- Make NOT NULL only after migration is complete
ALTER TABLE messages
ALTER COLUMN conversation_id SET NOT NULL;

-- Add the foreign key constraint
ALTER TABLE messages
ADD CONSTRAINT fk_messages_conversation_id
FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE; -- If a conversation is deleted, delete its messages


-- 5. Add indexes
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_chatbot_id ON conversations(chatbot_id);
CREATE INDEX IF NOT EXISTS idx_conversations_visitor_id ON conversations(visitor_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
-- Consider removing idx_messages_chatbot_id and idx_messages_visitor_id if queries always go via conversation_id now
-- DROP INDEX IF EXISTS idx_messages_chatbot_id;
-- DROP INDEX IF EXISTS idx_messages_visitor_id;


-- 6. Row-Level Security (RLS) for conversations table
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

-- Drop existing policies (if any) before creating new ones
DROP POLICY IF EXISTS "Chatbot owners can manage conversations" ON conversations;
DROP POLICY IF EXISTS "Service role can manage conversations" ON conversations;

-- Allow chatbot owners to view/update/delete their conversations
CREATE POLICY "Chatbot owners can manage conversations" ON conversations
  FOR ALL -- SELECT, INSERT, UPDATE, DELETE
  USING (auth.uid() = user_id) -- Checks apply to existing rows (SELECT, UPDATE, DELETE)
  WITH CHECK (auth.uid() = user_id); -- Checks apply to new/updated rows (INSERT, UPDATE)

-- Allow service_role full access
CREATE POLICY "Service role can manage conversations" ON conversations
  FOR ALL
  USING (current_setting('role') = 'service_role')
  WITH CHECK (current_setting('role') = 'service_role');


-- 7. Update RLS policies for messages table to use conversation_id
-- Drop old policies first
DROP POLICY IF EXISTS "Users can view messages for their chatbots" ON messages;
DROP POLICY IF EXISTS "Chatbot owners can update message read status" ON messages;
-- Keep the "Anyone can insert messages" policy for now, assuming your backend/chatbot logic handles authorization before insert.
-- If inserts should also be restricted, modify the insert policy.

-- New policy: Users can view messages belonging to their conversations
CREATE POLICY "Users can view messages in their conversations" ON messages
  FOR SELECT 
  USING (
    EXISTS (
      SELECT 1 FROM conversations c 
      WHERE c.id = messages.conversation_id AND c.user_id = auth.uid()
    )
  );

-- New policy: Users can update messages belonging to their conversations (e.g., mark as read)
CREATE POLICY "Users can update messages in their conversations" ON messages
  FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM conversations c 
      WHERE c.id = messages.conversation_id AND c.user_id = auth.uid()
    )
  )
  WITH CHECK ( -- Ensure the check matches the using clause for update
    EXISTS (
      SELECT 1 FROM conversations c 
      WHERE c.id = messages.conversation_id AND c.user_id = auth.uid()
    )
  );
  
-- New policy: Users can delete messages belonging to their conversations
-- Add this if users should be able to delete individual messages
CREATE POLICY "Users can delete messages in their conversations" ON messages
  FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM conversations c 
      WHERE c.id = messages.conversation_id AND c.user_id = auth.uid()
    )
  );


-- Optional: Consider a trigger to update conversations.last_message_at when a new message is inserted
-- CREATE OR REPLACE FUNCTION update_conversation_last_message_at()
-- RETURNS TRIGGER AS $$
-- BEGIN
--   UPDATE conversations
--   SET last_message_at = NEW.created_at, updated_at = NOW()
--   WHERE id = NEW.conversation_id;
--   RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql SECURITY DEFINER;

-- DROP TRIGGER IF EXISTS on_new_message_update_conversation ON messages;
-- CREATE TRIGGER on_new_message_update_conversation
--   AFTER INSERT ON messages
--   FOR EACH ROW EXECUTE FUNCTION update_conversation_last_message_at();


COMMIT; -- End transaction 