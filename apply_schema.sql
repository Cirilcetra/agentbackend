-- Create UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create users table to store authentication information
-- This extends the built-in Supabase auth.users
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY REFERENCES auth.users(id),
  username TEXT UNIQUE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create profiles table with user_id as primary key
CREATE TABLE IF NOT EXISTS profiles (
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
CREATE TABLE IF NOT EXISTS projects (
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
CREATE TABLE IF NOT EXISTS chatbots (
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
CREATE TABLE IF NOT EXISTS visitors (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  visitor_id TEXT NOT NULL UNIQUE,
  name TEXT,
  email TEXT,
  first_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create messages table with proper foreign keys
CREATE TABLE IF NOT EXISTS messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  chatbot_id UUID NOT NULL REFERENCES chatbots(id),
  visitor_id UUID REFERENCES visitors(id),
  message TEXT NOT NULL,
  response TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  is_read BOOLEAN DEFAULT FALSE
);

-- Row-level security (RLS) policies

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE chatbots ENABLE ROW LEVEL SECURITY;
ALTER TABLE visitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Users table policies
DROP POLICY IF EXISTS "Users can view their own data" ON users;
CREATE POLICY "Users can view their own data" ON users
  FOR SELECT USING (auth.uid() = id);

-- Allow service_role full access to users table
DROP POLICY IF EXISTS "Service role can manage users" ON users;
CREATE POLICY "Service role can manage users" ON users
  USING (current_setting('role') = 'service_role')
  WITH CHECK (current_setting('role') = 'service_role');
  
-- Allow backend API to create users via handle_new_user trigger
DROP POLICY IF EXISTS "Allow trigger to create users" ON users;
CREATE POLICY "Allow trigger to create users" ON users
  FOR INSERT WITH CHECK (true);

-- Profiles table policies
DROP POLICY IF EXISTS "Profiles are viewable by everyone" ON profiles;
CREATE POLICY "Profiles are viewable by everyone" ON profiles
  FOR SELECT USING (true);

DROP POLICY IF EXISTS "Users can update their own profile" ON profiles;
CREATE POLICY "Users can update their own profile" ON profiles
  FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own profile" ON profiles;
CREATE POLICY "Users can insert their own profile" ON profiles
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Allow service_role full access to profiles table
DROP POLICY IF EXISTS "Service role can manage profiles" ON profiles;
CREATE POLICY "Service role can manage profiles" ON profiles
  USING (current_setting('role') = 'service_role')
  WITH CHECK (current_setting('role') = 'service_role');

-- Projects table policies
DROP POLICY IF EXISTS "Projects are viewable by everyone" ON projects;
CREATE POLICY "Projects are viewable by everyone" ON projects
  FOR SELECT USING (true);

DROP POLICY IF EXISTS "Users can update their own projects" ON projects;
CREATE POLICY "Users can update their own projects" ON projects
  FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own projects" ON projects;
CREATE POLICY "Users can insert their own projects" ON projects
  FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own projects" ON projects;
CREATE POLICY "Users can delete their own projects" ON projects
  FOR DELETE USING (auth.uid() = user_id);

-- Chatbots table policies
DROP POLICY IF EXISTS "Public chatbots are viewable by everyone" ON chatbots;
CREATE POLICY "Public chatbots are viewable by everyone" ON chatbots
  FOR SELECT USING (is_public = true OR auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own chatbots" ON chatbots;
CREATE POLICY "Users can update their own chatbots" ON chatbots
  FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own chatbots" ON chatbots;
CREATE POLICY "Users can insert their own chatbots" ON chatbots
  FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own chatbots" ON chatbots;
CREATE POLICY "Users can delete their own chatbots" ON chatbots
  FOR DELETE USING (auth.uid() = user_id);

-- Visitors table policies
DROP POLICY IF EXISTS "Users can view visitors to their chatbots" ON visitors;
CREATE POLICY "Users can view visitors to their chatbots" ON visitors
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM messages m
      JOIN chatbots c ON m.chatbot_id = c.id
      WHERE m.visitor_id = visitors.id AND c.user_id = auth.uid()
    )
  );

-- Messages table policies
DROP POLICY IF EXISTS "Anyone can insert messages" ON messages;
CREATE POLICY "Anyone can insert messages" ON messages
  FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "Users can view messages for their chatbots" ON messages;
CREATE POLICY "Users can view messages for their chatbots" ON messages
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM chatbots
      WHERE chatbots.id = messages.chatbot_id AND chatbots.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "Chatbot owners can update message read status" ON messages;
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
CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_chatbots_user_id ON chatbots(user_id);
CREATE INDEX IF NOT EXISTS idx_chatbots_public_url_slug ON chatbots(public_url_slug);
CREATE INDEX IF NOT EXISTS idx_messages_chatbot_id ON messages(chatbot_id);
CREATE INDEX IF NOT EXISTS idx_messages_visitor_id ON messages(visitor_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

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

-- Drop the trigger if it exists to prevent errors on re-run
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

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
  ) ON CONFLICT (user_id) DO NOTHING;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create a trigger to create a profile when a new user is added to the users table
DROP TRIGGER IF EXISTS on_user_created ON users;
CREATE TRIGGER on_user_created
  AFTER INSERT ON users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user_profile();

-- Grant necessary privileges
GRANT SELECT, INSERT, UPDATE, DELETE ON users TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON profiles TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON projects TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON chatbots TO authenticated;
GRANT SELECT ON visitors TO authenticated;
GRANT SELECT, INSERT, UPDATE ON messages TO authenticated;

-- Grant service role all permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON users TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON profiles TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON projects TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON chatbots TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON visitors TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON messages TO service_role;

-- Allow anon to view public chatbots and insert messages
GRANT SELECT ON chatbots TO anon;
GRANT INSERT ON messages TO anon; 