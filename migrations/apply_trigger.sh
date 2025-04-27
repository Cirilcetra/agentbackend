#!/bin/bash

# Script to apply the user_signup_trigger.sql to the Supabase database

# Change to the migrations directory
cd "$(dirname "$0")"

# Make sure the SQL file exists
if [ ! -f "user_signup_trigger.sql" ]; then
    echo "Error: user_signup_trigger.sql file not found!"
    exit 1
fi

# Get Supabase URL and key from the environment or .env file
SUPABASE_URL=$(grep NEXT_PUBLIC_SUPABASE_URL ../../frontend/.env.local | cut -d '=' -f2)
SUPABASE_KEY=$(grep NEXT_PUBLIC_SUPABASE_ANON_KEY ../../frontend/.env.local | cut -d '=' -f2)

if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_KEY" ]; then
    echo "Error: Supabase URL or key not found in environment variables or .env file."
    echo "Please make sure they are set before running this script."
    exit 1
fi

echo "Supabase URL: $SUPABASE_URL"
echo "Going to apply the SQL trigger to your Supabase database..."
echo "Please open your Supabase dashboard in a browser and go to the SQL Editor."
echo ""
echo "Copy and paste the following SQL into the SQL Editor:"
echo "----------------------------------------"
cat user_signup_trigger.sql
echo "----------------------------------------"
echo ""
echo "After pasting, click the 'Run' button to apply the trigger."
echo ""
echo "Alternatively, you can use the Supabase CLI if you have it installed:"
echo "supabase db push user_signup_trigger.sql"

# Check if this is the Supabase project byddvbuzcgegasqeyuuc
if [[ "$SUPABASE_URL" == *"byddvbuzcgegasqeyuuc"* ]]; then
    echo ""
    echo "Detected Supabase project: byddvbuzcgegasqeyuuc"
    echo "Open the SQL Editor directly at:"
    echo "https://supabase.com/dashboard/project/byddvbuzcgegasqeyuuc/sql"
fi

echo ""
echo "When done, restart your application to ensure the changes take effect." 