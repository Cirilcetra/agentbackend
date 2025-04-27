-- Fix storage policies for profile-photos bucket

-- First check if the bucket exists, create it if it doesn't
DO $$
BEGIN
    -- Check if the profile-photos bucket already exists
    IF NOT EXISTS (
        SELECT 1 FROM storage.buckets WHERE name = 'profile-photos'
    ) THEN
        -- Create the profile-photos bucket if it doesn't exist
        INSERT INTO storage.buckets (id, name, public)
        VALUES ('profile-photos', 'profile-photos', true);
    END IF;
END
$$;

-- Create policies to allow service_role to manage profile-photos bucket
BEGIN;
    -- Drop existing policies first to avoid conflicts
    DROP POLICY IF EXISTS "Allow service role full access to profile-photos" ON storage.objects;
    
    -- Create policy for service_role to have full access
    -- Using `true` should grant broad access for the service role, potentially overriding other checks.
    CREATE POLICY "Allow service role full access to profile-photos" ON storage.objects
    FOR ALL
    USING ( (bucket_id = 'profile-photos') AND (auth.role() = 'service_role' OR auth.role() = 'supabase_admin') ) -- Use original condition for USING
    WITH CHECK (true); -- Use 'true' for WITH CHECK to allow inserts/updates broadly for service_role
COMMIT;

-- Create policy to allow users to upload their own profile photos
BEGIN;
    -- Drop existing policies first to avoid conflicts
    DROP POLICY IF EXISTS "Users can upload their own profile photos" ON storage.objects;
    
    -- Create policy for authenticated users to upload their own photos
    -- This allows users to upload to their own user_id folder
    CREATE POLICY "Users can upload their own profile photos" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'profile-photos' AND
        auth.uid()::text = (storage.foldername(name))[1]
    );
COMMIT;

-- Create policy to allow users to manage (update/delete) their own profile photos
BEGIN;
    -- Drop existing policies first to avoid conflicts
    DROP POLICY IF EXISTS "Users can manage their own profile photos" ON storage.objects;
    
    -- Create policy for authenticated users to manage their own photos
    CREATE POLICY "Users can manage their own profile photos" ON storage.objects
    FOR UPDATE USING (
        bucket_id = 'profile-photos' AND
        auth.uid()::text = (storage.foldername(name))[1]
    ) WITH CHECK (
        bucket_id = 'profile-photos' AND
        auth.uid()::text = (storage.foldername(name))[1]
    );
    
    -- Allow deletion of own photos
    DROP POLICY IF EXISTS "Users can delete their own profile photos" ON storage.objects;
    CREATE POLICY "Users can delete their own profile photos" ON storage.objects
    FOR DELETE USING (
        bucket_id = 'profile-photos' AND
        auth.uid()::text = (storage.foldername(name))[1]
    );
COMMIT;

-- Create policy to allow public access to profile photos (for viewing)
BEGIN;
    -- Drop existing policies first to avoid conflicts
    DROP POLICY IF EXISTS "Public access to profile photos" ON storage.objects;
    
    -- Create policy for public read access to all photos
    CREATE POLICY "Public access to profile photos" ON storage.objects
    FOR SELECT USING (bucket_id = 'profile-photos');
COMMIT;

-- Ensure the bucket is publicly accessible
UPDATE storage.buckets
SET public = true
WHERE name = 'profile-photos'; 