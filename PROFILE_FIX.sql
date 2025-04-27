-- Fix for profiles table to work with the application code
-- This handles the issue where the backend code references project_list field but database uses projects

-- Add project_list column as JSONB if it doesn't exist
ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS project_list JSONB DEFAULT '[]'::jsonb;

-- Add comment explaining the column
COMMENT ON COLUMN profiles.project_list IS 'Explicit JSONB array of projects for direct access, redundant with projects field';

-- Copy data from projects (text) to project_list (jsonb) for existing rows
UPDATE profiles
SET project_list = CASE 
                     WHEN projects IS NULL THEN '[]'::jsonb
                     WHEN projects = '' THEN '[]'::jsonb
                     ELSE projects::jsonb
                   END
WHERE project_list IS NULL OR project_list = '[]'::jsonb;

-- Create a function to keep projects and project_list in sync
CREATE OR REPLACE FUNCTION sync_profile_projects() RETURNS TRIGGER AS $$
BEGIN
  -- When project_list is updated, also update projects
  IF NEW.project_list IS DISTINCT FROM OLD.project_list THEN
    NEW.projects := NEW.project_list::text;
  END IF;
  
  -- When projects is updated, also update project_list
  IF NEW.projects IS DISTINCT FROM OLD.projects THEN
    BEGIN
      NEW.project_list := NEW.projects::jsonb;
    EXCEPTION WHEN others THEN
      -- If JSON parsing fails, set to empty array
      NEW.project_list := '[]'::jsonb;
    END;
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop the trigger if it exists
DROP TRIGGER IF EXISTS profile_projects_sync ON profiles;

-- Create the trigger
CREATE TRIGGER profile_projects_sync
BEFORE UPDATE ON profiles
FOR EACH ROW
EXECUTE FUNCTION sync_profile_projects(); 