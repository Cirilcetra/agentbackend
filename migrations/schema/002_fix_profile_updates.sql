-- Drop existing RLS policies for profiles
DROP POLICY IF EXISTS "Users can view their own profile" ON profiles;
DROP POLICY IF EXISTS "Users can update their own profile" ON profiles;
DROP POLICY IF EXISTS "Users can insert their own profile" ON profiles;

-- Create updated RLS policies for profiles
CREATE POLICY "Users can view their own profile"
  ON profiles FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can update their own profile"
  ON profiles FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own profile"
  ON profiles FOR INSERT
  WITH CHECK (auth.uid() = user_id);

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

-- Update existing profiles to NULL out any fields the user hasn't explicitly set
-- This will allow the application's defaults to be used instead of the hardcoded ones
UPDATE profiles
SET bio = NULL,
    skills = NULL,
    experience = NULL,
    interests = NULL
WHERE EXISTS (
  SELECT 1 FROM profiles p
  WHERE p.id = profiles.id
  AND p.bio = 'I am a software engineer with a passion for building AI and web applications. I specialize in full-stack development and have experience across the entire development lifecycle.'
  AND p.skills = 'JavaScript, TypeScript, React, Node.js, Python, FastAPI, PostgreSQL, ChromaDB, Supabase, Next.js, TailwindCSS'
  AND p.experience = '5+ years of experience in full-stack development, with a focus on building AI-powered applications and responsive web interfaces.'
  AND p.interests = 'AI, machine learning, web development, reading sci-fi, hiking'
); 