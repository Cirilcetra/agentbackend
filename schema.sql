-- Drop everything with CASCADE to forcefully remove all dependencies
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;

-- Create UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create users table to store authentication information
-- This extends the built-in Supabase auth.users
CREATE TABLE users (
  id UUID PRIMARY KEY REFERENCES auth.users(id),
  username TEXT UNIQUE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create profiles table with user_id as primary key
CREATE TABLE profiles (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id),
  name TEXT,
  location TEXT,
  bio TEXT NOT NULL DEFAULT 'No bio available yet.',
  skills TEXT NOT NULL DEFAULT 'No skills listed yet.',
  experience TEXT NOT NULL DEFAULT 'No experience listed yet.',
  interests TEXT NOT NULL DEFAULT 'No interests listed yet.',
  projects TEXT DEFAULT '[]', -- Store project_list as a JSON string
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  -- Add a unique constraint on user_id to ensure one profile per user
  UNIQUE(user_id)
);

-- Create projects table with foreign key to profiles
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id),
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  technologies TEXT,
  image_url TEXT,
  project_url TEXT,
  is_featured BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create chatbots table to define chatbots owned by users
CREATE TABLE chatbots (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id),
  name TEXT NOT NULL,
  description TEXT,
  is_public BOOLEAN DEFAULT TRUE,
  configuration JSONB DEFAULT '{}'::jsonb,
  public_url_slug TEXT UNIQUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create visitors table to track visitors to chatbots
CREATE TABLE visitors (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  visitor_id TEXT NOT NULL UNIQUE,
  name TEXT,
  email TEXT,
  first_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create messages table with proper foreign keys
CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  chatbot_id UUID NOT NULL REFERENCES chatbots(id),
  visitor_id UUID REFERENCES visitors(id),
  message TEXT NOT NULL,
  response TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  is_read BOOLEAN DEFAULT FALSE
);

-- Create notes table to store user notes
CREATE TABLE notes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id),
  content TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for faster note retrieval by user
CREATE INDEX idx_notes_user_id ON notes(user_id);

-- Enable RLS on notes table
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;

-- Notes table policies
CREATE POLICY "Users can view their own notes" ON notes
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own notes" ON notes
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own notes" ON notes
  FOR UPDATE USING (auth.uid() = user_id);

-- Function to delete a note (bypassing RLS)
CREATE OR REPLACE FUNCTION delete_note_privileged(p_note_id UUID, p_user_id UUID)
RETURNS BOOLEAN
SECURITY DEFINER
LANGUAGE plpgsql
AS $$
DECLARE
    affected_rows INTEGER;
BEGIN
    -- RLS is bypassed due to SECURITY DEFINER
    DELETE FROM public.notes
    WHERE id = p_note_id AND user_id = p_user_id
    RETURNING 1 INTO affected_rows;
    
    -- Return true if we deleted a row, false otherwise
    RETURN affected_rows > 0;
END;
$$;

-- Row-level security (RLS) policies

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE chatbots ENABLE ROW LEVEL SECURITY;
ALTER TABLE visitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Users table policies
CREATE POLICY "Users can view their own data" ON users
  FOR SELECT USING (auth.uid() = id);

-- Allow service_role full access to users table
CREATE POLICY "Service role can manage users" ON users
  USING (current_setting('role') = 'service_role')
  WITH CHECK (current_setting('role') = 'service_role');
  
-- Allow backend API to create users via handle_new_user trigger
CREATE POLICY "Allow trigger to create users" ON users
  FOR INSERT WITH CHECK (true);

-- Profiles table policies
CREATE POLICY "Profiles are viewable by everyone" ON profiles
  FOR SELECT USING (true);

CREATE POLICY "Users can update their own profile" ON profiles
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own profile" ON profiles
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Allow service_role full access to profiles table
CREATE POLICY "Service role can manage profiles" ON profiles
  USING (current_setting('role') = 'service_role')
  WITH CHECK (current_setting('role') = 'service_role');

-- Projects table policies
CREATE POLICY "Projects are viewable by everyone" ON projects
  FOR SELECT USING (true);

CREATE POLICY "Users can update their own projects" ON projects
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own projects" ON projects
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own projects" ON projects
  FOR DELETE USING (auth.uid() = user_id);

-- Chatbots table policies
CREATE POLICY "Public chatbots are viewable by everyone" ON chatbots
  FOR SELECT USING (is_public = true OR auth.uid() = user_id);

CREATE POLICY "Users can update their own chatbots" ON chatbots
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own chatbots" ON chatbots
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own chatbots" ON chatbots
  FOR DELETE USING (auth.uid() = user_id);

-- Visitors table policies
CREATE POLICY "Users can view visitors to their chatbots" ON visitors
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM messages m
      JOIN chatbots c ON m.chatbot_id = c.id
      WHERE m.visitor_id = visitors.id AND c.user_id = auth.uid()
    )
  );

-- Allow service_role full access to visitors table
CREATE POLICY "Service role can manage visitors" ON visitors
  USING (current_setting('role') = 'service_role')
  WITH CHECK (current_setting('role') = 'service_role');

-- Allow anonymous users to insert visitors (for first-time visitors)
CREATE POLICY "Anyone can insert visitors" ON visitors
  FOR INSERT WITH CHECK (true);

-- Messages table policies
CREATE POLICY "Anyone can insert messages" ON messages
  FOR INSERT WITH CHECK (true);

CREATE POLICY "Users can view messages for their chatbots" ON messages
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM chatbots
      WHERE chatbots.id = messages.chatbot_id AND chatbots.user_id = auth.uid()
    )
  );

CREATE POLICY "Chatbot owners can update message read status" ON messages
  FOR UPDATE USING (
    EXISTS (
      SELECT 1 FROM chatbots
      WHERE chatbots.id = messages.chatbot_id AND chatbots.user_id = auth.uid()
    )
  ) WITH CHECK (
    EXISTS (
      SELECT 1 FROM chatbots
      WHERE chatbots.id = messages.chatbot_id AND chatbots.user_id = auth.uid()
    )
  );

-- Create indexes for better performance
CREATE INDEX idx_profiles_user_id ON profiles(user_id);
CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_chatbots_user_id ON chatbots(user_id);
CREATE INDEX idx_chatbots_public_url_slug ON chatbots(public_url_slug);
CREATE INDEX idx_messages_chatbot_id ON messages(chatbot_id);
CREATE INDEX idx_messages_visitor_id ON messages(visitor_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);

-- Create trigger to automatically create a user entry when a new user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  -- Generate a username from the email if not provided in metadata
  DECLARE
    username_val TEXT;
  BEGIN
    -- Check if user_metadata contains a username
    IF new.raw_user_meta_data->>'username' IS NOT NULL THEN
      username_val := new.raw_user_meta_data->>'username';
    ELSE
      -- Extract username from email (the part before the @ symbol)
      username_val := SPLIT_PART(new.email, '@', 1);
    END IF;
    
    -- Insert new record into public.users
    INSERT INTO public.users(id, username, created_at, updated_at)
    VALUES (new.id, username_val, now(), now());
  END;
  
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create the trigger on auth.users table
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Create a trigger to automatically create a profile when a new user is created
CREATE OR REPLACE FUNCTION public.handle_new_user_profile()
RETURNS TRIGGER AS $$
BEGIN
  -- Create a default profile for the new user
  INSERT INTO public.profiles (user_id, bio, skills, experience, interests)
  VALUES (
    NEW.id,
    'I am a software engineer with a passion for building AI and web applications. I specialize in full-stack development and have experience across the entire development lifecycle.',
    'JavaScript, TypeScript, React, Node.js, Python, FastAPI, PostgreSQL, ChromaDB, Supabase, Next.js, TailwindCSS',
    '5+ years of experience in full-stack development, with a focus on building AI-powered applications and responsive web interfaces.',
    'AI, machine learning, web development, reading sci-fi, hiking'
  );
  
  -- Create a default chatbot for the user
  INSERT INTO public.chatbots (user_id, name, description, is_public, public_url_slug)
  VALUES (
    NEW.id,
    'My AI Assistant',
    'Personal AI assistant chatbot that knows about me and my projects',
    true,
    lower(NEW.username) -- Use lowercase username as URL slug
  );
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create the trigger on users table
CREATE TRIGGER on_user_created
  AFTER INSERT ON users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user_profile();

-- Helper functions

-- Function to get all messages for a specific chatbot
CREATE OR REPLACE FUNCTION get_chatbot_messages(chatbot_id UUID, limit_val INTEGER DEFAULT 50)
RETURNS SETOF messages AS $$
BEGIN
  RETURN QUERY
  SELECT *
  FROM messages
  WHERE messages.chatbot_id = get_chatbot_messages.chatbot_id
  ORDER BY created_at DESC
  LIMIT limit_val;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get a chatbot by its public URL slug
CREATE OR REPLACE FUNCTION get_chatbot_by_slug(slug TEXT)
RETURNS chatbots AS $$
DECLARE
  chat_bot chatbots;
BEGIN
  SELECT *
  INTO chat_bot
  FROM chatbots
  WHERE public_url_slug = slug AND is_public = true;
  
  RETURN chat_bot;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to mark messages as read
CREATE OR REPLACE FUNCTION mark_messages_as_read(chatbot_id_val UUID)
RETURNS VOID AS $$
BEGIN
  UPDATE messages
  SET is_read = true
  WHERE chatbot_id = chatbot_id_val AND is_read = false;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to generate a unique slug for chatbots
CREATE OR REPLACE FUNCTION generate_unique_slug(base_slug TEXT) 
RETURNS TEXT AS $$
DECLARE
  new_slug TEXT;
  counter INTEGER := 0;
  slug_exists BOOLEAN;
BEGIN
  -- Start with the base slug
  new_slug := base_slug;
  
  -- Check if it exists
  SELECT EXISTS(
    SELECT 1 FROM chatbots WHERE public_url_slug = new_slug
  ) INTO slug_exists;
  
  -- Keep generating new slugs until we find a unique one
  WHILE slug_exists LOOP
    counter := counter + 1;
    new_slug := base_slug || '-' || counter;
    
    SELECT EXISTS(
      SELECT 1 FROM chatbots WHERE public_url_slug = new_slug
    ) INTO slug_exists;
  END LOOP;
  
  RETURN new_slug;
END;
$$ LANGUAGE plpgsql;

-- Create helper view for message statistics
CREATE OR REPLACE VIEW message_stats AS
SELECT
  c.id AS chatbot_id,
  c.user_id,
  c.name AS chatbot_name,
  COUNT(m.id) AS total_messages,
  COUNT(DISTINCT m.visitor_id) AS unique_visitors,
  MAX(m.created_at) AS last_message_at
FROM
  chatbots c
LEFT JOIN
  messages m ON c.id = m.chatbot_id
GROUP BY
  c.id, c.user_id, c.name;

-- Grant necessary privileges
GRANT SELECT, INSERT, UPDATE, DELETE ON users TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON profiles TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON projects TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON chatbots TO authenticated;
GRANT SELECT ON visitors TO authenticated;
GRANT SELECT, INSERT, UPDATE ON messages TO authenticated;

-- Allow anon to view public chatbots and insert messages
GRANT SELECT ON chatbots TO anon;
GRANT INSERT ON messages TO anon;
GRANT INSERT ON visitors TO anon;
GRANT SELECT ON profiles TO anon;
GRANT SELECT ON projects TO anon;

-- Grant access to the helper functions
GRANT EXECUTE ON FUNCTION get_chatbot_messages TO authenticated;
GRANT EXECUTE ON FUNCTION get_chatbot_by_slug TO anon, authenticated;
GRANT EXECUTE ON FUNCTION mark_messages_as_read TO authenticated;
GRANT EXECUTE ON FUNCTION generate_unique_slug TO authenticated;

-- Grant service_role full access
GRANT SELECT, INSERT, UPDATE, DELETE ON users TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON profiles TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON projects TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON chatbots TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON visitors TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON messages TO service_role;

-- Add storage bucket RLS policies and the user_documents table

-- First, enable storage if not already enabled (this might need to be done in the Supabase dashboard)

-- Create user_documents table for document management
CREATE TABLE IF NOT EXISTS user_documents (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id),
  file_name TEXT NOT NULL,
  file_path TEXT NOT NULL,
  file_type TEXT,
  file_size INTEGER,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add index for better performance
CREATE INDEX IF NOT EXISTS idx_user_documents_user_id ON user_documents(user_id);

-- Enable RLS on the documents table
ALTER TABLE user_documents ENABLE ROW LEVEL SECURITY;

-- Create policies for user_documents table
DROP POLICY IF EXISTS "Users can view their own documents" ON user_documents;
CREATE POLICY "Users can view their own documents" ON user_documents
  FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own documents" ON user_documents;
CREATE POLICY "Users can insert their own documents" ON user_documents
  FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own documents" ON user_documents;
CREATE POLICY "Users can update their own documents" ON user_documents
  FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own documents" ON user_documents;
CREATE POLICY "Users can delete their own documents" ON user_documents
  FOR DELETE USING (auth.uid() = user_id);

-- Storage bucket policies
-- Note: This requires storage to be enabled in your Supabase project

-- Create policy to allow authenticated users to create buckets
BEGIN;
  DROP POLICY IF EXISTS "Allow users to create buckets" ON storage.buckets;
  CREATE POLICY "Allow users to create buckets" ON storage.buckets
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);
COMMIT;

-- Create policy to allow users to access buckets
BEGIN;
  DROP POLICY IF EXISTS "Allow users to select buckets" ON storage.buckets;
  CREATE POLICY "Allow users to select buckets" ON storage.buckets
    FOR SELECT USING (true);  -- Allow access to all buckets for simplicity
COMMIT;

-- Create policy for objects in storage
BEGIN;
  DROP POLICY IF EXISTS "Allow users to manage their own objects" ON storage.objects;
  CREATE POLICY "Allow users to manage their own objects" ON storage.objects
    FOR ALL USING (auth.uid() = owner OR bucket_id IN (SELECT name FROM storage.buckets WHERE name = 'documents'));
COMMIT;

-- Create policy to allow public access to documents
BEGIN;
  DROP POLICY IF EXISTS "Allow public access to documents bucket" ON storage.objects;
  CREATE POLICY "Allow public access to documents bucket" ON storage.objects
    FOR SELECT USING (bucket_id = 'documents');
COMMIT;

-- Explicitly grant all permissions to service role (critical fix)
-- This addresses the permission denied error for chatbots table
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO service_role;

-- Additionally, grant specific permissions to anon role for public operations
GRANT SELECT ON chatbots TO anon;
GRANT SELECT, INSERT ON messages TO anon;  
GRANT SELECT ON profiles TO anon;
GRANT SELECT ON projects TO anon;

-- Grant permissions for authenticated users
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;

-- Explicitly grant execute on all functions
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO authenticated;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO anon;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO service_role;