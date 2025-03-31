-- Create or replace a trigger function that automatically adds a record to users
-- when a new user signs up through Supabase Auth
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