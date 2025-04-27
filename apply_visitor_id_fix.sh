#!/bin/bash
# apply_visitor_id_fix.sh - Apply and verify the visitor ID fix

set -e  # Exit on any error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Applying Visitor ID Fix ===${NC}"
echo "This script will fix the visitor ID relationship between tables"

# Check for Python and required packages
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found. Please create it with SUPABASE_URL and SUPABASE_KEY${NC}"
    exit 1
fi

# Source the .env file to get credentials (if using bash)
source .env

# Check for required environment variables
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_KEY" ]; then
    echo -e "${RED}Error: SUPABASE_URL and SUPABASE_KEY must be set in .env file${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Installing required Python packages...${NC}"
pip install -q python-dotenv supabase

echo -e "${YELLOW}Step 2: Applying SQL fix...${NC}"
# Using the Supabase CLI if available, otherwise use Python
if command -v supabase &> /dev/null; then
    echo "Using Supabase CLI to apply SQL fix..."
    supabase db execute --file PROPER_VISITOR_ID_FIX.sql
else
    echo "Using Python to apply SQL fix..."
    python3 -c "
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

with open('PROPER_VISITOR_ID_FIX.sql', 'r') as f:
    sql = f.read()

result = supabase.rpc('query', {'query_text': sql}).execute()
print('SQL script executed successfully')
"
fi

echo -e "${YELLOW}Step 3: Verifying fix...${NC}"
python3 verify_visitor_id_fix.py

# Check if verification was successful
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Visitor ID fix has been successfully applied and verified!${NC}"
    echo -e "${GREEN}✅ The database now maintains proper referential integrity between visitors and messages tables.${NC}"
    
    # Update the database.py file if needed
    if [ -f app/database.py ]; then
        echo -e "${YELLOW}Step 4: Do you want to update the database.py file with the fixed implementation? (y/n)${NC}"
        read -r response
        if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            # Make a backup of the original file
            cp app/database.py app/database.py.bak.$(date +%Y%m%d%H%M%S)
            echo "Backup created at app/database.py.bak.$(date +%Y%m%d%H%M%S)"
            
            # Apply the changes to the database.py file
            echo "Applying changes to database.py..."
            
            # Since we can't easily modify the file in a bash script, provide instructions
            echo -e "${YELLOW}Please manually update the following functions in app/database.py:${NC}"
            echo "1. get_or_create_visitor() - Ensure it returns the visitor record with UUID"
            echo "2. log_chat_message() - Use visitor['id'] for messages.visitor_id"
            echo "See VISITOR_ID_IMPLEMENTATION.md for details"
        fi
    fi
    
    echo -e "${GREEN}Fix complete! You can now restart your backend application.${NC}"
else
    echo -e "${RED}❌ Verification failed. Please check the logs for errors.${NC}"
    exit 1
fi 