import os
import chromadb
import openai
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
import uuid
import time
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Mock embedding function for when OpenAI isn't available
class MockEmbeddingFunction:
    def __init__(self):
        logger.warning("Using mock embedding function - limited functionality will be available")
    
    def __call__(self, input):
        # Return a simple fixed-dimension vector for all inputs
        if isinstance(input, str):
            input = [input]
        return [[0.1] * 1536 for _ in input]  # OpenAI embeddings are 1536 dimensions

# Configure OpenAI with retry logic
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def setup_openai():
    api_key = os.environ.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("Missing OpenAI API key. Set OPENAI_API_KEY in Railway variables or .env file.")
        raise ValueError("Missing OpenAI API key. Set OPENAI_API_KEY in Railway variables or .env file.")
    openai.api_key = api_key
    logger.info("OpenAI API key configured successfully")
    return api_key

# Configure OpenAI with fallback for demo mode
openai_api_key = None
openai_available = False
try:
    openai_api_key = setup_openai()
    openai_available = True
    logger.info("OpenAI services initialized successfully")
except Exception as e:
    logger.error(f"Error setting up OpenAI: {e}")
    logger.warning("Running in DEMO MODE with limited functionality (no AI responses)")
    # Don't raise an error, continue with limited functionality

# Set up ChromaDB client with persistence for Railway
try:
    # For Railway, use in-memory store, as the filesystem is ephemeral
    if os.getenv("RAILWAY_ENVIRONMENT"):
        logger.info("Running in Railway environment, using in-memory ChromaDB")
        chroma_client = chromadb.Client()
    else:
        # For local development, use persistent directory
        persist_dir = os.path.join(os.getcwd(), "chroma_db")
        if not os.path.exists(persist_dir):
            os.makedirs(persist_dir)
        logger.info(f"Using persistent ChromaDB directory: {persist_dir}")
        chroma_client = chromadb.PersistentClient(path=persist_dir)
    
    logger.info("ChromaDB client initialized successfully")
except Exception as e:
    logger.error(f"Error initializing ChromaDB: {e}")
    # Fallback to in-memory client if persistent fails
    chroma_client = chromadb.Client()
    logger.warning("Falling back to in-memory ChromaDB client")

# Create embedding function using OpenAI embeddings or fallback to mock
# Use a custom embedding function compatible with OpenAI v1.x
class OpenAIEmbeddingFunction:
    def __init__(self, api_key, model_name="text-embedding-ada-002"):
        self.api_key = api_key
        self.model_name = model_name
        
    def __call__(self, input):
        # Ensure input is a list
        if isinstance(input, str):
            input = [input]
        
        # Get embeddings from OpenAI
        response = openai.embeddings.create(
            model=self.model_name,
            input=input
        )
        
        # Extract embeddings from response
        embeddings = [item.embedding for item in response.data]
        return embeddings

if openai_available:
    # Initialize custom embedding function
    openai_ef = OpenAIEmbeddingFunction(api_key=openai.api_key)
    logger.info("Using OpenAI embedding function")
else:
    # Use mock embedding function
    openai_ef = MockEmbeddingFunction()
    logger.warning("Using mock embedding function - search will have limited accuracy")

# Create or get collection
try:
    portfolio_collection = chroma_client.get_or_create_collection(
        name="portfolio_data",
        embedding_function=openai_ef
    )
    logger.info("Portfolio collection initialized")
except Exception as e:
    logger.error(f"Error creating collection: {e}")
    # Create a minimal interface to avoid breaking calls
    from types import SimpleNamespace
    portfolio_collection = SimpleNamespace(
        query=lambda **kwargs: {"documents": [[]], "metadatas": [[]], "distances": [[]]},
        add=lambda **kwargs: None,
        delete=lambda **kwargs: None,
        count=lambda: 0
    )
    logger.warning("Using mock collection - functionality will be limited")

def add_profile_to_vector_db(profile_data, user_id=None):
    """
    Add profile data to the vector database
    Note: user_id param is kept for compatibility but we use a single collection for now
    """
    try:
        # For simplicity, we'll use a single collection for all profiles
        collection_name = "portfolio_data"
        print(f"Using collection name: {collection_name}")
        
        # Create or get the appropriate collection
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=openai_ef
        )
        
        # Clear existing documents from this collection
        try:
            collection.delete(where={"category": {"$eq": "profile"}})
            print(f"Cleared existing profile documents from collection {collection_name}")
        except Exception as clear_error:
            print(f"Error clearing collection (may be empty): {clear_error}")
        
        # Format and add new documents
        documents = []
        metadatas = []
        ids = []
        
        # Add name
        if profile_data.get("name"):
            documents.append(profile_data["name"])
            metadatas.append({"category": "profile", "subcategory": "name"})
            ids.append("name")
        
        # Add location
        if profile_data.get("location"):
            documents.append(profile_data["location"])
            metadatas.append({"category": "profile", "subcategory": "location"})
            ids.append("location")
        
        # Add bio
        if profile_data.get("bio"):
            documents.append(profile_data["bio"])
            metadatas.append({"category": "profile", "subcategory": "bio"})
            ids.append("bio")
        
        # Add skills
        if profile_data.get("skills"):
            documents.append(profile_data["skills"])
            metadatas.append({"category": "profile", "subcategory": "skills"})
            ids.append("skills")
        
        # Add experience
        if profile_data.get("experience"):
            documents.append(profile_data["experience"])
            metadatas.append({"category": "profile", "subcategory": "experience"})
            ids.append("experience")
        
        # Add legacy projects text if it exists
        if profile_data.get("projects"):
            documents.append(profile_data["projects"])
            metadatas.append({"category": "profile", "subcategory": "projects"})
            ids.append("projects")
        
        # Add interests
        if profile_data.get("interests"):
            documents.append(profile_data["interests"])
            metadatas.append({"category": "profile", "subcategory": "interests"})
            ids.append("interests")
        
        # Add documents to collection
        if documents:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Successfully added {len(documents)} profile documents to vector database")
            
        # Now add projects from project_list if available
        add_projects_to_vector_db(profile_data.get("project_list", []))
        
        return True
    except Exception as e:
        print(f"Error adding profile to vector database: {e}")
        return False

def add_projects_to_vector_db(projects_list):
    """
    Add project items to the vector database
    """
    if not projects_list:
        print("No projects to add to vector database")
        return True
        
    try:
        # Use the same collection for projects
        collection_name = "portfolio_data"
        print(f"Using collection name for projects: {collection_name}")
        
        # Create or get the appropriate collection
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=openai_ef
        )
        
        # Clear existing project documents from this collection
        try:
            collection.delete(where={"category": {"$eq": "project"}})
            print(f"Cleared existing project documents from collection {collection_name}")
        except Exception as clear_error:
            print(f"Error clearing project documents (may be empty): {clear_error}")
        
        # Format and add new documents for each project
        documents = []
        metadatas = []
        ids = []
        
        for project in projects_list:
            project_id = project.get("id")
            if not project_id:
                continue
                
            # Add project title
            if project.get("title"):
                documents.append(project["title"])
                metadatas.append({
                    "category": "project", 
                    "subcategory": "title",
                    "project_id": project_id,
                    "project_category": project.get("category", "")
                })
                ids.append(f"project_title_{project_id}")
            
            # Add project description
            if project.get("description"):
                documents.append(project["description"])
                metadatas.append({
                    "category": "project", 
                    "subcategory": "description",
                    "project_id": project_id,
                    "project_category": project.get("category", "")
                })
                ids.append(f"project_description_{project_id}")
                
            # Add project details
            if project.get("details"):
                documents.append(project["details"])
                metadatas.append({
                    "category": "project", 
                    "subcategory": "details",
                    "project_id": project_id,
                    "project_category": project.get("category", "")
                })
                ids.append(f"project_details_{project_id}")
                
            # Add project content - supporting both Lexical and legacy content
            content_text = ""
            
            # Handle Lexical content format (JSON with HTML representation)
            if project.get("content"):
                try:
                    # Try to use content_html if available
                    if project.get("content_html"):
                        # Strip HTML tags for indexing
                        content_text = project["content_html"]
                        # Simple HTML tag removal for indexing purposes
                        import re
                        content_text = re.sub(r'<[^>]*>', ' ', content_text)
                    else:
                        # Try to parse Lexical JSON
                        import json
                        content_data = json.loads(project["content"])
                        if content_data.get("html"):
                            content_text = content_data["html"]
                            # Simple HTML tag removal for indexing purposes
                            import re
                            content_text = re.sub(r'<[^>]*>', ' ', content_text)
                        else:
                            # Fallback to raw content
                            content_text = project["content"]
                except Exception as e:
                    # If not JSON or parsing fails, use raw content
                    print(f"Warning: Could not parse project content as JSON: {e}")
                    content_text = project["content"]
            
            # If we have content, add it to the vector DB
            if content_text:
                # Split content into smaller chunks if it's too large
                if len(content_text) > 1000:
                    # Split into ~1000 character chunks with some overlap
                    chunk_size = 1000
                    overlap = 100
                    chunks = []
                    for i in range(0, len(content_text), chunk_size - overlap):
                        chunk = content_text[i:i + chunk_size]
                        if chunk:
                            chunks.append(chunk)
                    
                    # Add each chunk as a separate document
                    for i, chunk in enumerate(chunks):
                        documents.append(chunk)
                        metadatas.append({
                            "category": "project", 
                            "subcategory": "content",
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "project_id": project_id,
                            "project_category": project.get("category", "")
                        })
                        ids.append(f"project_content_{project_id}_{i}")
                else:
                    # Add the whole content as one document
                    documents.append(content_text)
                    metadatas.append({
                        "category": "project", 
                        "subcategory": "content",
                        "project_id": project_id,
                        "project_category": project.get("category", "")
                    })
                    ids.append(f"project_content_{project_id}")
        
        # Add documents to collection
        if documents:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Successfully added {len(documents)} project documents to vector database")
        
        return True
    except Exception as e:
        print(f"Error adding projects to vector database: {e}")
        return False

def add_conversation_to_vector_db(message, response, visitor_id, message_id=None):
    """
    Add conversation exchange to the vector database for future context retrieval
    """
    try:
        # Use the portfolio collection for simplicity, but with different category
        collection_name = "portfolio_data"
        print(f"Adding conversation to collection: {collection_name}")
        
        # Create or get the appropriate collection
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=openai_ef
        )
        
        # Generate a unique ID if not provided
        if not message_id:
            message_id = str(uuid.uuid4())
        
        # Format the conversation as a complete exchange for context
        conversation_text = f"User asked: {message}\nYou responded: {response}"
        
        # Add to vector DB
        collection.add(
            documents=[conversation_text],
            metadatas=[{
                "category": "conversation",
                "subcategory": "exchange",
                "visitor_id": visitor_id,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }],
            ids=[f"conversation_{message_id}"]
        )
        
        print(f"Successfully added conversation exchange to vector database")
        return True
    except Exception as e:
        print(f"Error adding conversation to vector database: {e}")
        return False

def query_vector_db(query, n_results=3, user_id=None, visitor_id=None, include_conversation=True):
    """
    Query the vector database with the user's question
    If include_conversation is True and visitor_id is provided, will also search conversation history
    """
    try:
        # Use a single collection for all users
        collection_name = "portfolio_data"
        print(f"Querying collection: {collection_name}")
        
        # Get or create the collection
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=openai_ef
        )
        
        # Check if collection is empty
        collection_count = collection.count()
        if collection_count == 0:
            print("Vector database is empty, returning empty results")
            return {
                "documents": [],
                "metadatas": [],
                "distances": []
            }
        
        # Query collection with query text
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where=({"category": {"$ne": "conversation"}} if not include_conversation else None)
        )
        
        # If visitor_id is provided and include_conversation is True,
        # also search for relevant conversation history
        if visitor_id and include_conversation:
            print(f"Also searching conversation history for visitor: {visitor_id}")
            conversation_results = collection.query(
                query_texts=[query],
                n_results=3,  # Get top 3 relevant conversation exchanges
                where={"category": "conversation", "visitor_id": visitor_id}
            )
            
            # Append conversation results if any found
            if conversation_results and len(conversation_results.get("documents", [[]])[0]) > 0:
                print(f"Found {len(conversation_results['documents'][0])} relevant conversation exchanges")
                
                # Add to results
                for i, doc in enumerate(conversation_results["documents"][0]):
                    results["documents"][0].append(doc)
                    results["metadatas"][0].append(conversation_results["metadatas"][0][i])
                    results["distances"][0].append(conversation_results["distances"][0][i])
        
        # Extract and structure results
        query_results = {
            "documents": results.get("documents", [[]])[0],
            "metadatas": results.get("metadatas", [[]])[0],
            "distances": results.get("distances", [[]])[0]
        }
        
        print(f"Query '{query}' returned {len(query_results['documents'])} total results")
        return query_results
    except Exception as e:
        print(f"Error querying vector database: {e}")
        return {
            "documents": [],
            "metadatas": [],
            "distances": []
        }

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def call_openai_api(system_prompt, query):
    """Call OpenAI API with retry logic"""
    if not openai_available:
        return "I'm sorry, but the AI service is currently in demo mode and cannot generate responses. Please configure your OpenAI API key."
    
    response = openai.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        temperature=0.3,  # Lower temperature to minimize creativity
        max_tokens=500
    )
    return response.choices[0].message.content

def generate_ai_response(query, search_results, profile_data=None, chat_history=None):
    """
    Generate a response using OpenAI based on the query and search results
    If profile_data is provided, use it to personalize the response
    If chat_history is provided, include it for conversation context
    """
    # If OpenAI is not available, return a demo mode message
    if not openai_available:
        return "I'm sorry, but the AI service is currently in demo mode due to missing API keys. Please configure your OpenAI API key in Railway variables or .env file."
    
    # Combine search results into context
    context = ""
    if search_results["documents"] and len(search_results["documents"]) > 0 and len(search_results["documents"][0]) > 0:
        for i, doc in enumerate(search_results["documents"][0]):
            subcategory = search_results["metadatas"][0][i]["subcategory"]
            context += f"{subcategory.upper()}: {doc}\n\n"
        logger.info(f"Found {len(search_results['documents'][0])} relevant context items from vector database")
    else:
        # If no results, use a default message
        context = "No specific information available. Please provide a general response."
        logger.warning("No vector DB results to include in context - response will be limited")
    
    # Extract name from profile data for better personalization
    user_name = profile_data.get('name', '') if profile_data else ''
    if not user_name and profile_data and profile_data.get('bio'):
        # Try to extract name from bio if name field is empty
        bio = profile_data.get('bio', '')
        if 'I am ' in bio:
            try:
                name_part = bio.split('I am ')[1].split(' ')[0]
                if len(name_part) > 2:  # Ensure it's likely a name, not just "a" or "an"
                    user_name = name_part
            except:
                pass
    
    # Create a comprehensive profile context
    profile_context = ""
    if profile_data:
        # Extract key information from profile for context
        profile_context = f"""
NAME: {profile_data.get('name', 'Not provided')}
LOCATION: {profile_data.get('location', 'Not provided')}
BIO: {profile_data.get('bio', 'Not provided')}
SKILLS: {profile_data.get('skills', 'Not provided')}
EXPERIENCE: {profile_data.get('experience', 'Not provided')}
PROJECTS: {profile_data.get('projects', 'Not provided')}
INTERESTS: {profile_data.get('interests', 'Not provided')}
        """
        logger.info(f"Added complete profile data to context ({len(profile_context.split())} words)")
        
        # Log a summary of available profile fields for debugging
        available_fields = [field for field in ['name', 'location', 'bio', 'skills', 'experience', 'projects', 'interests'] 
                          if profile_data.get(field)]
        logger.info(f"Available profile fields: {', '.join(available_fields)}")
    else:
        logger.warning("No profile data available - responses will be generic")
    
    # Format conversation history if provided
    conversation_context = ""
    if chat_history and len(chat_history) > 0:
        logger.info(f"Including {len(chat_history)} messages from conversation history")
        conversation_context = "PREVIOUS CONVERSATION:\n"
        for i, msg in enumerate(chat_history):
            if msg.get('sender') == 'user':
                conversation_context += f"Visitor: {msg.get('message', '')}\n"
            else:
                conversation_context += f"You: {msg.get('response', '')}\n"
        conversation_context += "\n"
    else:
        logger.info("No conversation history provided")
    
    # Create a strongly worded system prompt that clearly instructs the AI to respond as the user
    system_prompt = f"""
You are NOT an AI assistant. You ARE {user_name or "the person"} whose profile information is provided below.

When responding, you MUST:
1. Speak in the FIRST PERSON (I, me, my) as if you ARE this person.
2. ONLY use the exact information provided in the context sections below.
3. DO NOT invent, add, or make up ANY details that aren't explicitly mentioned in the provided profile information.
4. If you don't have specific information to answer a question, say "I prefer not to discuss that topic" rather than making up a response.
5. Match the tone and style that would be natural for a professional with this background.
6. Never break character or refer to yourself as an AI.
7. Never apologize for "not having information" - instead, redirect to what you do know from the profile.
8. STICK STRICTLY to the information provided - do not elaborate with invented details.
9. Maintain consistency with previous responses in the conversation history.

YOUR PROFILE INFORMATION:
{profile_context}

{conversation_context}

RELEVANT PROFILE SECTIONS THAT MATCH THIS QUERY:
{context}

Remember: You ARE this person, but you can ONLY respond with information that is explicitly mentioned in the above sections.
If asked about something not covered in the profile information, politely redirect or state you prefer to focus on the topics listed.
    """
    
    # Generate response
    try:
        logger.info("Sending chat completion request to OpenAI with strict context-only instructions")
        return call_openai_api(system_prompt, query)
    except openai.APIError as e:
        logger.error(f"OpenAI API Error: {str(e)}")
        return f"I'm sorry, I couldn't generate a response at the moment due to an API error. Please try again later."
    except openai.APIConnectionError as e:
        logger.error(f"OpenAI API Connection Error: {str(e)}")
        return f"I'm sorry, I couldn't connect to the response service. Please check your internet connection and try again."
    except openai.RateLimitError as e:
        logger.error(f"OpenAI Rate Limit Error: {str(e)}")
        return f"I'm sorry, the service is currently experiencing high demand. Please try again in a few moments."
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return "I'm sorry, I couldn't generate a response at the moment. Please try again later." 