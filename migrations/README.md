# Database Migrations

This directory contains SQL files for database migrations.

## How to Apply Migrations

### User Signup Trigger

The `user_signup_trigger.sql` file contains a trigger that automatically creates a record in the `users` table when a new user signs up through Supabase Auth.

To apply this trigger, follow these steps:

1. Log in to the Supabase dashboard
2. Go to the SQL Editor
3. Copy the contents of `user_signup_trigger.sql`
4. Paste the SQL into the SQL Editor
5. Click "Run" to execute the SQL

Alternatively, you can use the Supabase CLI with:

```bash
supabase db push user_signup_trigger.sql
```

## Testing the Trigger

After applying the trigger, you can test it by:

1. Creating a new user through the Supabase Auth UI or API
2. Checking the `users` table to confirm a new record was created
3. Verify that the username was correctly extracted from the email or user metadata 