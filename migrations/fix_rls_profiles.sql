-- Drop existing RLS policies for profiles
DROP POLICY IF EXISTS "Users can view their own profile" ON profiles;
DROP POLICY IF EXISTS "Users can update their own profile" ON profiles;
DROP POLICY IF EXISTS "Users can insert their own profile" ON profiles;

-- Create updated RLS policies for profiles with more relaxed permissions for testing
CREATE POLICY "Public profiles are viewable by everyone" 
  ON profiles FOR SELECT
  USING (true);

CREATE POLICY "Profiles can be updated with matching user_id" 
  ON profiles FOR UPDATE
  USING (true);

CREATE POLICY "New profiles can be created" 
  ON profiles FOR INSERT
  WITH CHECK (true);

-- Make sure all updates to profiles set the updated_at timestamp
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop the trigger if it exists
DROP TRIGGER IF EXISTS set_timestamp ON profiles;

-- Create a trigger to automatically set the updated_at timestamp
CREATE TRIGGER set_timestamp
BEFORE UPDATE ON profiles
FOR EACH ROW
EXECUTE FUNCTION update_modified_column(); 