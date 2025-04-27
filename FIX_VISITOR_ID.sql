-- FIX_VISITOR_ID.sql
-- This script modifies the database to correctly handle visitor IDs in the messages table
-- The issue is that the application is storing visitor_id as a string (TEXT) but trying to query it as UUID

-- 1. First, determine if visitor_summary view exists and drop it if so
DROP VIEW IF EXISTS visitor_summary;

-- 2. Make sure the visitor_id_text column exists in messages table
ALTER TABLE messages ADD COLUMN IF NOT EXISTS visitor_id_text TEXT;

-- 3. Create an index on visitor_id_text for better query performance
CREATE INDEX IF NOT EXISTS idx_messages_visitor_id_text ON messages(visitor_id_text);

-- 4. Add a comment explaining the purpose of the visitor_id_text column
COMMENT ON COLUMN messages.visitor_id_text IS 'Stores the original frontend visitor ID string for direct lookup without joins';

-- 5. Now we can safely alter the visitors table's visitor_id column to TEXT
ALTER TABLE visitors ALTER COLUMN visitor_id TYPE TEXT;

-- 6. Create a function to query messages by visitor_id_text
CREATE OR REPLACE FUNCTION get_messages_by_visitor_text(visitor_text TEXT, limit_val INTEGER DEFAULT 50)
RETURNS SETOF messages AS $$
BEGIN
  RETURN QUERY 
  SELECT * FROM messages 
  WHERE visitor_id_text = visitor_text
  ORDER BY created_at DESC
  LIMIT limit_val;
END;
$$ LANGUAGE plpgsql;

-- 7. Add a comment explaining the purpose of the function
COMMENT ON FUNCTION get_messages_by_visitor_text IS 'Retrieves messages using visitor_id_text instead of visitor_id UUID';

-- 8. Update existing messages records to populate visitor_id_text from the original visitor_id
-- This ensures all existing records are accessible with the new query approach
UPDATE messages m
SET visitor_id_text = v.visitor_id
FROM visitors v
WHERE m.visitor_id = v.id
AND m.visitor_id_text IS NULL;

-- 9. If needed, recreate the visitor_summary view with the updated column types
-- Adjust this view definition based on your actual requirements
CREATE OR REPLACE VIEW visitor_summary AS
SELECT 
    v.id AS visitor_db_id,
    v.visitor_id AS visitor_external_id,
    COUNT(m.id) AS message_count,
    MIN(m.created_at) AS first_message,
    MAX(m.created_at) AS last_message,
    COUNT(DISTINCT CASE WHEN m.response IS NOT NULL THEN m.id END) AS response_count
FROM 
    visitors v
LEFT JOIN 
    messages m ON v.id = m.visitor_id
GROUP BY 
    v.id, v.visitor_id;

-- 10. Add an index to the visitors table on visitor_id to speed up lookups
CREATE INDEX IF NOT EXISTS idx_visitors_visitor_id ON visitors(visitor_id);

-- 11. Reminder: The application code needs to be updated to use visitor_id_text for queries
-- This SQL script only handles the database schema changes
COMMENT ON TABLE messages IS 'Application should query messages using visitor_id_text instead of visitor_id UUID';

-- These commands are for interactive psql and don't work in SQL scripts:
-- \d messages
-- \d visitors 