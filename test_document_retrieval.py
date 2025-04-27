import os
import sys
import json
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import required functions
try:
    from app.embeddings import query_vector_db, generate_ai_response
    from app.database import get_profile_data
except ImportError as e:
    print(f"Failed to import required modules: {e}")
    sys.exit(1)

async def test_document_retrieval(user_id, query):
    """Test document retrieval and AI response generation"""
    print(f"\n=== Testing Document Retrieval ===")
    print(f"User ID: {user_id}")
    print(f"Query: {query}\n")
    
    # Step 1: Get profile data
    print("Getting profile data...")
    profile_data = get_profile_data(user_id=user_id)
    
    if not profile_data:
        print(f"No profile found for user {user_id}")
        return
        
    print(f"Found profile for {profile_data.get('name')}")
    
    # Step 2: Query the vector database
    print("\nQuerying vector database...")
    search_results = query_vector_db(
        query=query,
        user_id=user_id,
        visitor_id=None,
        include_conversation=True
    )
    
    # Step 3: Generate AI response
    print("\nGenerating AI response...")
    response = await generate_ai_response(
        message=query,
        search_results=search_results,
        profile_data=profile_data,
        chat_history=[]
    )
    
    # Print results
    print("\n=== Results ===")
    print(f"AI Response:\n{response}")
    
    return response

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_document_retrieval.py <user_id> <query>")
        print("Example: python test_document_retrieval.py 9837e518-80f6-46d4-9aec-cf60c0d8be37 'What medical conditions can you treat?'")
        sys.exit(1)
        
    user_id = sys.argv[1]
    query = sys.argv[2]
    
    # Run the test
    asyncio.run(test_document_retrieval(user_id, query)) 