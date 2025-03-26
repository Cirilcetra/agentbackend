-- Create UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing tables to recreate with proper structure
DROP TABLE IF EXISTS profiles CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS projects CASCADE;
DROP TABLE IF EXISTS chatbots CASCADE;
DROP TABLE IF EXISTS admin_users CASCADE;

-- Create profiles table with user_id to link to auth.users
CREATE TABLE profiles (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  bio TEXT,
  skills TEXT,
  experience TEXT,
  interests TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id)
);

-- Create projects table to store user projects
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  technologies TEXT,
  image_url TEXT,
  project_url TEXT,
  is_featured BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create chatbots table to store user's chatbot configurations
CREATE TABLE chatbots (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  is_public BOOLEAN DEFAULT FALSE,
  configuration JSONB DEFAULT '{}',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create messages table for chat history
CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  chatbot_id UUID REFERENCES chatbots(id) ON DELETE CASCADE,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  visitor_id TEXT,
  visitor_name TEXT,
  message TEXT NOT NULL,
  response TEXT,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security on all tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE chatbots ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Create indexes for better performance
CREATE INDEX idx_profiles_user_id ON profiles(user_id);
CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_chatbots_user_id ON chatbots(user_id);
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_messages_chatbot_id ON messages(chatbot_id);
CREATE INDEX idx_messages_visitor_id ON messages(visitor_id);

-- RLS Policies for profiles
CREATE POLICY "Users can view their own profile"
  ON profiles FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can update their own profile"
  ON profiles FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can insert their own profile"
  ON profiles FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- RLS Policies for projects
CREATE POLICY "Users can manage their own projects"
  ON projects FOR ALL
  USING (auth.uid() = user_id);

-- RLS Policies for chatbots
CREATE POLICY "Users can manage their own chatbots"
  ON chatbots FOR ALL
  USING (auth.uid() = user_id);

CREATE POLICY "Anyone can view public chatbots"
  ON chatbots FOR SELECT
  USING (is_public = true OR auth.uid() = user_id);

-- RLS Policies for messages
CREATE POLICY "Users can see messages from their chatbots"
  ON messages FOR SELECT
  USING (
    auth.uid() = user_id OR 
    auth.uid() IN (
      SELECT c.user_id FROM chatbots c WHERE c.id = messages.chatbot_id
    )
  );

CREATE POLICY "Users can insert messages to their chatbots"
  ON messages FOR INSERT
  WITH CHECK (
    auth.uid() = user_id OR 
    auth.uid() IN (
      SELECT c.user_id FROM chatbots c WHERE c.id = messages.chatbot_id
    ) OR
    chatbot_id IN (
      SELECT id FROM chatbots WHERE is_public = true
    )
  );

CREATE POLICY "Anonymous users can insert messages to public chatbots"
  ON messages FOR INSERT
  WITH CHECK (
    auth.uid() IS NULL AND
    chatbot_id IN (
      SELECT id FROM chatbots WHERE is_public = true
    )
  );

-- Grant access to the tables
GRANT SELECT, INSERT, UPDATE, DELETE ON profiles TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON projects TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON chatbots TO authenticated;
GRANT SELECT, INSERT ON messages TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON messages TO authenticated;

-- Function to create profile after signup
CREATE OR REPLACE FUNCTION public.handle_new_user() 
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (user_id)
  VALUES (NEW.id);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to create profile after signup
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Grant usage on sequences to make autogeneration work
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated; 