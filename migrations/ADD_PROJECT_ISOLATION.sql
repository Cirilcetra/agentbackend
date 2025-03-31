-- Add database configuration and searchable content columns to projects table
ALTER TABLE projects 
ADD COLUMN IF NOT EXISTS database_config JSONB DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS searchable_content TSVECTOR;

-- Create a GIN index for full-text search
CREATE INDEX IF NOT EXISTS projects_searchable_content_idx ON projects USING GIN(searchable_content);

-- Create a function to update searchable content
CREATE OR REPLACE FUNCTION update_project_searchable_content()
RETURNS TRIGGER AS $$
BEGIN
  NEW.searchable_content = 
    setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'B') ||
    setweight(to_tsvector('english', COALESCE(NEW.technologies, '')), 'C');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update searchable content
DROP TRIGGER IF EXISTS project_search_update ON projects;
CREATE TRIGGER project_search_update
  BEFORE INSERT OR UPDATE ON projects
  FOR EACH ROW
  EXECUTE FUNCTION update_project_searchable_content();

-- Add RLS policies for projects
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

-- Allow users to view their own projects
CREATE POLICY "Users can view their own projects"
  ON projects FOR SELECT
  USING (auth.uid() = user_id);

-- Allow users to insert their own projects
CREATE POLICY "Users can insert their own projects"
  ON projects FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Allow users to update their own projects
CREATE POLICY "Users can update their own projects"
  ON projects FOR UPDATE
  USING (auth.uid() = user_id);

-- Allow users to delete their own projects
CREATE POLICY "Users can delete their own projects"
  ON projects FOR DELETE
  USING (auth.uid() = user_id); 