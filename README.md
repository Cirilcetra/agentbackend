# AI Agent Backend

A FastAPI backend for an AI agent chatbot with profile management, powered by OpenAI and Supabase.

## Recent Updates

### Multi-User Support Implementation

The backend has been updated to support multiple users with the following changes:

1. **User-Specific Profiles**: Each user now has their own profile data, stored with their `user_id`.
2. **User-Specific Vector Collections**: ChromaDB collections are now created per-user, allowing for personalized AI responses.
3. **Improved Database Schema**: Updated the Supabase schema to support attaching profiles to specific users.
4. **Targeted Chatbot Responses**: Chat requests can now target specific users via the `target_user_id` parameter.
5. **Enhanced Security**: Added user authentication and authorization for sensitive operations.
6. **Improved Error Handling**: More robust error handling for database and API operations.
7. **Conversation History**: Chat history is now stored and retrieved per user.

These improvements allow multiple users to have their own AI agents that respond based on their specific profile data, creating a more personalized experience.

## Local Development

1. Clone the repository
2. Create a `.env` file based on `.env.example`
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the development server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Railway Deployment

### Important: Environment Variables Setup

Setting up environment variables correctly is **critical** for the application to function properly. There are several ways to add environment variables in Railway:

#### Method 1: Railway Dashboard (Recommended)

1. Go to the [Railway Dashboard](https://railway.app/dashboard)
2. Select your project and service
3. Navigate to the "Variables" tab
4. Add each of these required variables:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_KEY`: Your Supabase anon/public key
   - `DATABASE_URL`: Your PostgreSQL connection string
   - `FRONTEND_URL`: The URL of your frontend application (for CORS)
5. Click "Deploy" to apply the changes

#### Method 2: Deploy via GitHub Integration

1. Fork this repository
2. Create a new project in Railway
3. Connect your GitHub repository
4. **Crucially**: Add environment variables in Railway dashboard (as described in Method 1)
5. Deploy

#### Method 3: Deploy via Railway CLI

1. Install Railway CLI:
   ```bash
   npm i -g @railway/cli
   ```
2. Login to Railway:
   ```bash
   railway login
   ```
3. Link to your Railway project:
   ```bash
   railway link
   ```
4. Set up environment variables:
   ```bash
   railway variables set OPENAI_API_KEY=your_api_key
   railway variables set SUPABASE_URL=your_supabase_url
   railway variables set SUPABASE_KEY=your_supabase_key
   railway variables set DATABASE_URL=your_database_url
   # Add other variables as needed
   ```
5. Deploy your project:
   ```bash
   railway up
   ```

### Troubleshooting Environment Variables

If your application is running in "demo mode" with messages about missing API keys:

1. Verify the variables are correctly set in the Railway dashboard
2. Check for any typos in the variable names (they are case-sensitive)
3. Make sure you've redeployed after adding the variables
4. Check the deployment logs for any error messages
5. Try setting the variables using a different method (dashboard vs CLI)

### Environment Variables Required for Railway

- `OPENAI_API_KEY`: Your OpenAI API key
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Your Supabase anon/public key (not the service role key)
- `DATABASE_URL`: PostgreSQL connection string
- `FRONTEND_URL`: The URL of your frontend application (for CORS)

### Security Note

**IMPORTANT**: Never commit API keys or secrets to your Git repository. Always use the Railway dashboard or CLI to set these values.

## API Documentation

Once deployed, access the API documentation at:
- Swagger UI: `/docs`
- ReDoc: `/redoc` 