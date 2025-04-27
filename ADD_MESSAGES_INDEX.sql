-- Add index on target_user_id for better performance
CREATE INDEX IF NOT EXISTS idx_messages_target_user_id ON messages(target_user_id);

-- Add index on combined fields for better filtering
CREATE INDEX IF NOT EXISTS idx_messages_combined ON messages(chatbot_id, visitor_id, target_user_id);

-- Add index on created_at DESC for better sorting
CREATE INDEX IF NOT EXISTS idx_messages_created_at_desc ON messages(created_at DESC);

-- Force cache refresh
NOTIFY pgrst, 'reload config'; 