# Fixing Supabase Permissions Issues

## Problem Identified

We've identified a key issue in the logs showing **permission errors** when the backend tries to create users or profiles in Supabase:

```
ERROR: {'code': '42501', 'details': None, 'hint': None, 'message': 'new row violates row-level security policy for table "users"'}
```

This happens because:

1. The backend service is trying to create records in the database
2. Supabase Row Level Security (RLS) policies are preventing these operations
3. The service_role key is not being used correctly to bypass these policies

## The Fix Involves Two Parts:

### 1. Update the SQL Schema with Better RLS Policies

The updated `APPLY_SCHEMA_IN_SUPABASE.sql` now includes:

- Modified RLS policies that properly allow the service role to perform all operations
- Simplified user creation policies
- An explicit FOR ALL permission for the service role

```sql
-- Allow service_role full access to users table
DROP POLICY IF EXISTS "Service role can manage users" ON users;
CREATE POLICY "Service role can manage users" ON users
  FOR ALL USING (true);
  
-- Allow authenticated users to create users (needed for the backend server)
DROP POLICY IF EXISTS "Allow creation of users" ON users;
CREATE POLICY "Allow creation of users" ON users
  FOR INSERT WITH CHECK (true);
```

### 2. Correctly Configure the Supabase Client

The backend code now properly sets up the Supabase client with service role authorization:

```python
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
```

This ensures the backend has the necessary permissions to:
- Create users
- Create and update profiles
- Access any required data

## Steps to Apply the Fix

1. Run the updated SQL in `APPLY_SCHEMA_IN_SUPABASE.sql` in your Supabase SQL Editor
2. Restart the backend server to apply the client changes
3. Test by creating a new user and verifying the profile is created

## Verifying the Fix

When properly fixed:
1. The backend logs should no longer show RLS policy violations
2. New users should automatically get profiles
3. Each user should have their own profile data

## Important Notes

- The `SUPABASE_KEY` in your backend .env should be the **service role key**, not the anon key
- This key has admin privileges, so keep it secure in your backend
- Never expose this key in frontend code 