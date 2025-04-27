-- COMPLETE FIX for profiles table schema
-- This script handles adding the project_list column and provides a full solution

-- Step 1: Check which columns exist in the profiles table
DO $$
DECLARE
  projects_exists BOOLEAN;
  project_list_exists BOOLEAN;
BEGIN
  -- Check if projects column exists
  SELECT EXISTS (
    SELECT FROM information_schema.columns 
    WHERE table_name = 'profiles' AND column_name = 'projects'
  ) INTO projects_exists;
  
  -- Check if project_list column exists
  SELECT EXISTS (
    SELECT FROM information_schema.columns 
    WHERE table_name = 'profiles' AND column_name = 'project_list'
  ) INTO project_list_exists;
  
  -- Output the current state
  RAISE NOTICE 'Current state: projects column exists: %, project_list column exists: %', 
    projects_exists, project_list_exists;
    
  -- Add project_list column if it doesn't exist
  IF NOT project_list_exists THEN
    RAISE NOTICE 'Adding project_list column to profiles table';
    EXECUTE 'ALTER TABLE profiles ADD COLUMN project_list JSONB DEFAULT ''[]''::jsonb';
    
    -- Add comment to the column
    EXECUTE 'COMMENT ON COLUMN profiles.project_list IS ''JSON array of projects for compatibility with application code''';
  END IF;
  
  -- Sync data from projects to project_list if both columns exist
  IF projects_exists AND project_list_exists THEN
    RAISE NOTICE 'Syncing data from projects to project_list';
    BEGIN
      EXECUTE 'UPDATE profiles SET project_list = CASE 
                 WHEN projects IS NULL THEN ''[]''::jsonb
                 WHEN projects = '''' THEN ''[]''::jsonb
                 ELSE projects::jsonb
               END 
               WHERE project_list IS NULL OR project_list = ''[]''::jsonb';
    EXCEPTION WHEN OTHERS THEN
      RAISE NOTICE 'Error syncing data: %', SQLERRM;
    END;
  END IF;
  
  -- Create trigger function if both columns exist
  IF projects_exists AND project_list_exists THEN
    RAISE NOTICE 'Creating sync function and trigger';
    
    -- Create or replace the function
    CREATE OR REPLACE FUNCTION sync_profile_projects() 
    RETURNS TRIGGER AS $FUNC$
    BEGIN
      -- When project_list is updated, also update projects
      IF NEW.project_list IS DISTINCT FROM OLD.project_list THEN
        NEW.projects := NEW.project_list::text;
      END IF;
      
      -- When projects is updated, also update project_list
      IF NEW.projects IS DISTINCT FROM OLD.projects THEN
        BEGIN
          NEW.project_list := NEW.projects::jsonb;
        EXCEPTION WHEN OTHERS THEN
          -- If JSON parsing fails, set to empty array
          NEW.project_list := '[]'::jsonb;
        END;
      END IF;
      
      RETURN NEW;
    END;
    $FUNC$ LANGUAGE plpgsql;
    
    -- Drop existing trigger if it exists
    DROP TRIGGER IF EXISTS profile_projects_sync ON profiles;
    
    -- Create the trigger
    CREATE TRIGGER profile_projects_sync
    BEFORE UPDATE ON profiles
    FOR EACH ROW
    EXECUTE FUNCTION sync_profile_projects();
  END IF;
END $$;

-- Show results for verification
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'profiles' 
ORDER BY ordinal_position; 