-- Add visitor_id_text column to messages table
ALTER TABLE messages ADD COLUMN IF NOT EXISTS visitor_id_text TEXT;

-- Create index on the new column for better query performance
CREATE INDEX IF NOT EXISTS idx_messages_visitor_id_text ON messages(visitor_id_text);

-- Explain the purpose of the column
COMMENT ON COLUMN messages.visitor_id_text IS 'Stores the original frontend visitor ID string for direct lookup without joins'; 