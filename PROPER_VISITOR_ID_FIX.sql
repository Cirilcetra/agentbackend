-- PROPER_VISITOR_ID_FIX.sql
-- This script fixes the visitor_id relationship between visitors and messages tables
-- Ensuring proper referential integrity while maintaining backward compatibility

-- First, check current schema to understand the state
DO $$ 
DECLARE
  messages_visitor_id_type TEXT;
  visitors_id_type TEXT;
  visitors_visitor_id_type TEXT;
  visitor_id_text_exists BOOLEAN;
BEGIN
  -- Get current column types
  SELECT data_type INTO messages_visitor_id_type FROM information_schema.columns 
  WHERE table_name = 'messages' AND column_name = 'visitor_id';
  
  SELECT data_type INTO visitors_id_type FROM information_schema.columns 
  WHERE table_name = 'visitors' AND column_name = 'id';
  
  SELECT data_type INTO visitors_visitor_id_type FROM information_schema.columns 
  WHERE table_name = 'visitors' AND column_name = 'visitor_id';
  
  -- Check if visitor_id_text exists
  SELECT EXISTS (
    SELECT FROM information_schema.columns 
    WHERE table_name = 'messages' AND column_name = 'visitor_id_text'
  ) INTO visitor_id_text_exists;

  -- Output current state
  RAISE NOTICE 'Current schema state:';
  RAISE NOTICE '- messages.visitor_id type: %', messages_visitor_id_type;
  RAISE NOTICE '- visitors.id type: %', visitors_id_type;
  RAISE NOTICE '- visitors.visitor_id type: %', visitors_visitor_id_type;
  RAISE NOTICE '- messages.visitor_id_text exists: %', visitor_id_text_exists;
END $$;

-- Step 1: Ensure visitor_id_text column exists in messages table
ALTER TABLE messages ADD COLUMN IF NOT EXISTS visitor_id_text TEXT;

-- Step 2: Create index on visitor_id_text for query performance
CREATE INDEX IF NOT EXISTS idx_messages_visitor_id_text ON messages(visitor_id_text);

-- Step 3: Add explanatory comment to visitor_id_text column
COMMENT ON COLUMN messages.visitor_id_text IS 'Stores the original frontend visitor ID string for direct lookup';

-- Step 4: Ensure visitors.visitor_id is TEXT type to match frontend format
-- Skip if already TEXT type
DO $$ 
BEGIN
  IF EXISTS (
    SELECT FROM information_schema.columns 
    WHERE table_name = 'visitors' AND column_name = 'visitor_id'
    AND data_type <> 'text'
  ) THEN
    RAISE NOTICE 'Converting visitors.visitor_id to TEXT type';
    ALTER TABLE visitors ALTER COLUMN visitor_id TYPE TEXT;
  END IF;
END $$;

-- Step 5: Reset messages.visitor_id to be UUID type (if it's not already)
-- This is the proper foreign key to visitors.id
DO $$ 
BEGIN
  IF EXISTS (
    SELECT FROM information_schema.columns 
    WHERE table_name = 'messages' AND column_name = 'visitor_id'
    AND data_type <> 'uuid'
  ) THEN
    RAISE NOTICE 'Converting messages.visitor_id back to UUID type';
    
    -- First drop any existing foreign key constraints
    -- We'll recreate them later
    EXECUTE (
      SELECT 'ALTER TABLE messages DROP CONSTRAINT ' || constraint_name
      FROM information_schema.table_constraints
      WHERE table_name = 'messages'
      AND constraint_type = 'FOREIGN KEY'
      AND constraint_name LIKE '%visitor_id%'
      LIMIT 1
    );
    
    -- Convert column type
    ALTER TABLE messages ALTER COLUMN visitor_id TYPE UUID USING NULL;
  END IF;
END $$;

-- Step 6: Copy data from visitor_id_text to visitor_id where possible
-- For each message, look up the visitor by visitor_id_text and set the proper visitor.id
UPDATE messages m
SET visitor_id = v.id
FROM visitors v
WHERE m.visitor_id_text = v.visitor_id
AND m.visitor_id IS NULL;

-- Step 7: Recreate the foreign key constraint
ALTER TABLE messages 
DROP CONSTRAINT IF EXISTS messages_visitor_id_fkey;

ALTER TABLE messages
ADD CONSTRAINT messages_visitor_id_fkey
FOREIGN KEY (visitor_id) REFERENCES visitors(id);

-- Step 8: Create helpful functions for querying messages by visitor_id_text
CREATE OR REPLACE FUNCTION get_messages_by_visitor_text(visitor_text TEXT, limit_val INTEGER DEFAULT 50)
RETURNS SETOF messages AS $$
BEGIN
  RETURN QUERY 
  SELECT m.* FROM messages m
  JOIN visitors v ON m.visitor_id = v.id
  WHERE v.visitor_id = visitor_text
  ORDER BY m.created_at DESC
  LIMIT limit_val;
END;
$$ LANGUAGE plpgsql;

-- Step 9: Add helpful comment to the function
COMMENT ON FUNCTION get_messages_by_visitor_text IS 'Retrieves messages by looking up the visitor_id_text through proper visitor join';

-- Step 10: Add helpful index for lookups
CREATE INDEX IF NOT EXISTS idx_visitors_visitor_id ON visitors(visitor_id);

-- Output final state for verification
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_name IN ('visitors', 'messages')
AND column_name IN ('id', 'visitor_id', 'visitor_id_text')
ORDER BY table_name, column_name; 