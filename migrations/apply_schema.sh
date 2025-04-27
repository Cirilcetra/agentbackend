#!/bin/bash

# Script to apply new_schema.sql to the Supabase database

# Change to the root directory
cd "$(dirname "$0")"
cd ..

# Make sure the SQL file exists
if [ ! -f "new_schema.sql" ]; then
    echo "Error: new_schema.sql file not found!"
    exit 1
fi

# Extract Supabase URL and API key from .env file
SUPABASE_URL=$(grep SUPABASE_URL .env | cut -d '=' -f2)
SUPABASE_KEY=$(grep SUPABASE_KEY .env | cut -d '=' -f2)

if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_KEY" ]; then
    echo "Error: Supabase URL or key not found in .env file."
    echo "Please make sure they are set before running this script."
    exit 1
fi

echo "Supabase URL: $SUPABASE_URL"
echo "Going to apply the new schema to your Supabase database..."
echo "Please open your Supabase dashboard in a browser and go to the SQL Editor."
echo ""
echo "Copy and paste the following SQL into the SQL Editor:"
echo "----------------------------------------"
cat new_schema.sql
echo "----------------------------------------"
echo ""
echo "After pasting, click the 'Run' button to apply the schema."
echo ""
echo "Important Notes:"
echo "1. This will create or update the necessary tables for the application."
echo "2. Each user will now have their own profile data."
echo "3. After applying the schema, restart the backend server."
echo ""
echo "When done, restart your application to ensure the changes take effect." 