# AI Agent Backend

A FastAPI backend for an AI agent chatbot with profile management, powered by OpenAI and Supabase.

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

### Option 1: Deploy via GitHub Integration

1. Fork this repository
2. Create a new project in Railway
3. Connect your GitHub repository
4. Add environment variables in Railway dashboard (copy from `.env.sample`)
5. Deploy

### Option 2: Deploy via Railway CLI

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
   railway vars set OPENAI_API_KEY=your_api_key
   railway vars set SUPABASE_URL=your_supabase_url
   railway vars set SUPABASE_KEY=your_supabase_key
   # Add other variables as needed
   ```
5. Deploy your project:
   ```bash
   railway up
   ```

### Environment Variables Required for Railway

- `OPENAI_API_KEY`: Your OpenAI API key
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Your Supabase project API key
- `FRONTEND_URL`: The URL of your frontend application (for CORS)
- `DATABASE_URL`: PostgreSQL connection string (if using external database)

## API Documentation

Once deployed, access the API documentation at:
- Swagger UI: `/docs`
- ReDoc: `/redoc` 