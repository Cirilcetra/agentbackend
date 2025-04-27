import os
import chromadb
import openai
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
import uuid
import time
from typing import List

# Load environment variables
load_dotenv()

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("Missing OpenAI API key. Set OPENAI_API_KEY in .env file.")

# Set up ChromaDB client
# Use persistent storage instead of in-memory
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
# Ensure the directory exists
os.makedirs(CHROMA_DB_PATH, exist_ok=True)
# Use persistent storage rather than in-memory
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
print(f"ChromaDB client initialized with persistent storage at: {CHROMA_DB_PATH}")

# Create embedding function using OpenAI embeddings
# Use a custom embedding function compatible with OpenAI v1.x
class OpenAIEmbeddingFunction:
    def __init__(self, api_key, model_name="text-embedding-ada-002"):
        self.api_key = api_key
        self.model_name = model_name
        
    def __call__(self, input):
        # Ensure input is a list
        if isinstance(input, str):
            input = [input]
        
        try:
            # Get embeddings from OpenAI
            response = openai.embeddings.create(
                model=self.model_name,
                input=input
            )
            
            # Extract embeddings from response
            embeddings = [item.embedding for item in response.data]
            return embeddings
        except Exception as e:
            print(f"Error generating embeddings: {str(e)}")
            # Return a simple embedding with zeros to avoid crashing
            # This is a fallback for when the OpenAI API fails
            return [[0.0] * 1536] * len(input)  # 1536 is the dimension for ada-002 embeddings

# Initialize custom embedding function
openai_ef = OpenAIEmbeddingFunction(api_key=openai.api_key)

# Create or get collection
portfolio_collection = chroma_client.get_or_create_collection(
    name="portfolio_data",
    embedding_function=openai_ef
)

def add_profile_to_vector_db(profile_data, user_id=None):
    """
    Add profile data to the vector database
    Includes user_id in metadata to allow filtering by specific user
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
        
        # Extract user ID from profile data if not explicitly provided
        effective_user_id = user_id or profile_data.get("user_id")
        
        if not effective_user_id:
            print("Warning: No user_id provided for vector DB entry. Profile data will not be user-specific.")
            effective_user_id = "default"
        else:
            print(f"Adding profile data to vector DB for user_id: {effective_user_id}")
        
        # Clear existing profile documents for this specific user
        try:
            collection.delete(where={
                "$and": [
                    {"category": {"$eq": "profile"}},
                    {"user_id": {"$eq": effective_user_id}}
                ]
            })
            print(f"Cleared existing profile documents for user {effective_user_id}")
        except Exception as clear_error:
            print(f"Error clearing collection (may be empty): {clear_error}")
        
        # Format and add new documents
        documents = []
        metadatas = []
        ids = []
        
        # Add name
        if profile_data.get("name"):
            documents.append(profile_data["name"])
            metadatas.append({"category": "profile", "subcategory": "name", "user_id": effective_user_id})
            ids.append(f"name_{effective_user_id}")
        
        # Add location
        if profile_data.get("location"):
            documents.append(profile_data["location"])
            metadatas.append({"category": "profile", "subcategory": "location", "user_id": effective_user_id})
            ids.append(f"location_{effective_user_id}")
        
        # Add bio
        if profile_data.get("bio"):
            documents.append(profile_data["bio"])
            metadatas.append({"category": "profile", "subcategory": "bio", "user_id": effective_user_id})
            ids.append(f"bio_{effective_user_id}")
        
        # Add skills
        if profile_data.get("skills"):
            documents.append(profile_data["skills"])
            metadatas.append({"category": "profile", "subcategory": "skills", "user_id": effective_user_id})
            ids.append(f"skills_{effective_user_id}")
        
        # Add experience
        if profile_data.get("experience"):
            documents.append(profile_data["experience"])
            metadatas.append({"category": "profile", "subcategory": "experience", "user_id": effective_user_id})
            ids.append(f"experience_{effective_user_id}")
        
        # Add interests
        if profile_data.get("interests"):
            documents.append(profile_data["interests"])
            metadatas.append({"category": "profile", "subcategory": "interests", "user_id": effective_user_id})
            ids.append(f"interests_{effective_user_id}")
        
        # Add documents to collection
        if documents:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Successfully added {len(documents)} profile documents to vector database for user {effective_user_id}")
            
        return True
    except Exception as e:
        print(f"Error adding profile to vector database: {e}")
        return False

def add_conversation_to_vector_db(message, response, visitor_id, message_id=None, user_id=None):
    """
    Add conversation snippets to the vector database for RAG.
    Include user_id to ensure proper segregation of conversation data by chatbot owner
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
        
        # Create metadata with user_id if provided
        metadata = {
            "category": "conversation",
            "subcategory": "exchange",
            "visitor_id": visitor_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Add user_id if provided
        if user_id:
            metadata["user_id"] = user_id
            print(f"Including user_id {user_id} in conversation metadata")
        
        # Add to vector DB
        collection.add(
            documents=[conversation_text],
            metadatas=[metadata],
            ids=[f"conversation_{message_id}"]
        )
        
        print(f"Successfully added conversation exchange to vector database")
        return True
    except Exception as e:
        print(f"Error adding conversation to vector database: {e}")
        return False

def add_document_to_vector_db(document_data, user_id):
    """
    Add document content to the vector database for chatbot context
    The document_data should contain the extracted text and metadata
    """
    try:
        # Use the same collection as profile and project data
        collection_name = "portfolio_data"
        print(f"Adding document content to collection: {collection_name}")
        
        # Create or get the collection
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=openai_ef
        )
        
        document_id = document_data.get("id")
        if not document_id:
            print("Warning: Document has no ID, generating a random one")
            document_id = str(uuid.uuid4())
            
        # Get the extracted text from the document
        extracted_text = document_data.get("extracted_text", "")
        if not extracted_text:
            print("Warning: Document has no extracted text to add to vector DB")
            return False
            
        title = document_data.get("title", "Untitled Document")
        
        print(f"Adding document '{title}' to vector DB for user_id: {user_id}")
        
        # Format and add new documents
        documents = []
        metadatas = []
        ids = []
        
        # Add document title and metadata
        documents.append(f"Document Title: {title}")
        metadatas.append({
            "category": "document",
            "subcategory": "title",
            "document_id": document_id,
            "user_id": user_id
        })
        ids.append(f"document_title_{document_id}_{user_id}")
        
        # If document has a description, add it too
        description = document_data.get("description")
        if description:
            documents.append(f"Document Description: {description}")
            metadatas.append({
                "category": "document", 
                "subcategory": "description",
                "document_id": document_id,
                "user_id": user_id
            })
            ids.append(f"document_description_{document_id}_{user_id}")
        
        # Split content into smaller chunks if it's too large
        if len(extracted_text) > 1000:
            # Split into ~1000 character chunks with some overlap
            chunk_size = 1000
            overlap = 100
            chunks = []
            
            for i in range(0, len(extracted_text), chunk_size - overlap):
                chunk = extracted_text[i:i + chunk_size]
                if chunk:
                    chunks.append(chunk)
            
            # Add each chunk as a separate document
            for i, chunk in enumerate(chunks):
                documents.append(chunk)
                metadatas.append({
                    "category": "document", 
                    "subcategory": "content",
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "document_id": document_id,
                    "title": title,
                    "user_id": user_id
                })
                ids.append(f"document_content_{document_id}_{i}_{user_id}")
        else:
            # Add the whole content as one document
            documents.append(extracted_text)
            metadatas.append({
                "category": "document", 
                "subcategory": "content",
                "document_id": document_id,
                "title": title,
                "user_id": user_id
            })
            ids.append(f"document_content_{document_id}_{user_id}")
        
        # Add documents to collection
        if documents:
            print(f"Adding {len(documents)} documents to vector DB:")
            for i, doc_id in enumerate(ids):
                print(f"  ID {i}: {doc_id}")
                
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Successfully added {len(documents)} document chunks to vector database")
            
        return True
    except Exception as e:
        print(f"Error adding document to vector database: {e}")
        return False

def query_vector_db(query, n_results=8, user_id=None, visitor_id=None, include_conversation=True):
    """
    Query the vector database with the user's question
    If include_conversation is True and visitor_id is provided, will also search conversation history
    """
    try:
        # Use a single collection for all users
        collection_name = "portfolio_data"
        print(f"Querying collection: {collection_name} with query: '{query}'")
        
        # Get or create the collection
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=openai_ef
        )
        
        # Check if collection is empty
        collection_count = collection.count()
        if collection_count == 0:
            print(f"Vector database is empty (count: 0), returning empty results")
            return {
                "documents": [],
                "metadatas": [],
                "distances": []
            }
        
        print(f"Collection has {collection_count} total documents")
        
        # Create combined results structure
        combined_docs = []
        combined_meta = []
        combined_dist = []
        
        # Track what types of content we found
        found_types = {"document": False, "profile": False, "project": False, "conversation": False}
        
        # First, try to get document content specifically with higher n_results
        if user_id:
            try:
                print(f"Searching for document content with user_id: {user_id}")
                document_filter = {
                    "$and": [
                        {"category": {"$eq": "document"}},
                        {"user_id": {"$eq": user_id}}
                    ]
                }
                
                # First check if any documents exist
                doc_count_results = collection.get(
                    where=document_filter,
                    limit=1
                )
                
                if len(doc_count_results.get("ids", [])) > 0:
                    print(f"Found documents for user {user_id}, performing query")
                    # Set a reasonable n_results value (between 5-10 is good)
                    doc_n_results = 8
                    
                    document_results = collection.query(
                        query_texts=[query],
                        n_results=doc_n_results,
                        where=document_filter
                    )
                    
                    if document_results and len(document_results.get("documents", [[]])[0]) > 0:
                        document_count = len(document_results["documents"][0])
                        print(f"Found {document_count} relevant document chunks from query")
                        found_types["document"] = True
                        
                        # Add documents to combined results
                        for i, doc in enumerate(document_results["documents"][0]):
                            metadata = document_results["metadatas"][0][i]
                            dist = document_results["distances"][0][i] if document_results.get("distances") else 1.0
                            print(f"  Doc #{i+1}: {metadata.get('subcategory')} - {doc[:50]}... (distance: {dist:.4f})")
                            
                            # Add to combined results
                            combined_docs.append(doc)
                            combined_meta.append(metadata)
                            combined_dist.append(dist)
                    else:
                        print("No relevant document results found for the query")
                else:
                    print(f"No documents found for user {user_id}")
            except Exception as doc_error:
                print(f"Error searching document content: {str(doc_error)}")
        
        # Then, get profile data
        if user_id:
            try:
                profile_filter = {
                    "$and": [
                        {"category": {"$eq": "profile"}},
                        {"user_id": {"$eq": user_id}}
                    ]
                }
                
                # Check if any profile data exists
                profile_count_results = collection.get(
                    where=profile_filter,
                    limit=1
                )
                
                if len(profile_count_results.get("ids", [])) > 0:
                    print(f"Found profile data for user {user_id}, performing query")
                    
                    profile_results = collection.query(
                        query_texts=[query],
                        n_results=n_results,
                        where=profile_filter
                    )
                    
                    if profile_results and len(profile_results.get("documents", [[]])[0]) > 0:
                        profile_count = len(profile_results["documents"][0])
                        print(f"Found {profile_count} relevant profile entries")
                        found_types["profile"] = True
                        
                        # Add to combined results
                        for i, doc in enumerate(profile_results["documents"][0]):
                            combined_docs.append(doc)
                            combined_meta.append(profile_results["metadatas"][0][i])
                            combined_dist.append(profile_results["distances"][0][i])
                else:
                    print(f"No profile data found for user {user_id}")
            except Exception as profile_error:
                print(f"Error searching profile data: {str(profile_error)}")
        
        # Get project data
        if user_id:
            try:
                project_filter = {
                    "$and": [
                        {"category": {"$eq": "project"}},
                        {"user_id": {"$eq": user_id}}
                    ]
                }
                
                # Check if any project data exists
                project_count_results = collection.get(
                    where=project_filter,
                    limit=1
                )
                
                if len(project_count_results.get("ids", [])) > 0:
                    print(f"Found project data for user {user_id}, performing query")
                    
                    project_results = collection.query(
                        query_texts=[query],
                        n_results=n_results,
                        where=project_filter
                    )
                    
                    if project_results and len(project_results.get("documents", [[]])[0]) > 0:
                        project_count = len(project_results["documents"][0])
                        print(f"Found {project_count} relevant project entries")
                        found_types["project"] = True
                        
                        # Add to combined results
                        for i, doc in enumerate(project_results["documents"][0]):
                            combined_docs.append(doc)
                            combined_meta.append(project_results["metadatas"][0][i])
                            combined_dist.append(project_results["distances"][0][i])
                else:
                    print(f"No project data found for user {user_id}")
            except Exception as project_error:
                print(f"Error searching project data: {str(project_error)}")
        
        # If visitor_id is provided and include_conversation is True,
        # also search for relevant conversation history
        if visitor_id and include_conversation:
            try:
                conversation_filter = {
                    "$and": [
                        {"category": {"$eq": "conversation"}},
                        {"visitor_id": {"$eq": visitor_id}}
                    ]
                }
                
                # Check if any conversation history exists
                conv_count_results = collection.get(
                    where=conversation_filter,
                    limit=1
                )
                
                if len(conv_count_results.get("ids", [])) > 0:
                    print(f"Found conversation data for visitor {visitor_id}, performing query")
                
                conversation_results = collection.query(
                    query_texts=[query],
                    n_results=3,  # Get top 3 relevant conversation exchanges
                    where=conversation_filter
                )
                
                if conversation_results and len(conversation_results.get("documents", [[]])[0]) > 0:
                    print(f"Found {len(conversation_results['documents'][0])} relevant conversation exchanges")
                    found_types["conversation"] = True
                    
                    # Add to combined results
                    for i, doc in enumerate(conversation_results["documents"][0]):
                        combined_docs.append(doc)
                        combined_meta.append(conversation_results["metadatas"][0][i])
                        combined_dist.append(conversation_results["distances"][0][i])
                else:
                    print(f"No conversation history found for visitor {visitor_id}")
            except Exception as conv_error:
                print(f"Error fetching conversation history: {str(conv_error)}")
        
        # If we have no results at all, try a general query
        if not combined_docs:
            print("No specific results found, trying general query")
            try:
                # We can't specify n_results > collection_count, so limit it
                safe_n_results = min(n_results, collection_count)
                
                general_results = collection.query(
                    query_texts=[query],
                    n_results=safe_n_results
                )
                
                if general_results and len(general_results.get("documents", [[]])[0]) > 0:
                    general_count = len(general_results["documents"][0])
                    print(f"Found {general_count} results from general query")
                    
                    # Add to combined results, filtering by user_id if provided
                    for i, doc in enumerate(general_results["documents"][0]):
                        meta = general_results["metadatas"][0][i]
                        # Only add if user_id matches or is not provided
                        if not user_id or meta.get("user_id") == user_id:
                            combined_docs.append(doc)
                            combined_meta.append(meta)
                            combined_dist.append(general_results["distances"][0][i])
            except Exception as general_error:
                print(f"Error in general query: {str(general_error)}")
        
        # Print a summary of what we found
        found_summary = []
        for content_type, found in found_types.items():
            if found:
                found_summary.append(content_type)
        
        if found_summary:
            print(f"Found content types: {', '.join(found_summary)}")
        else:
            print("No relevant content found")
        
        # Sort combined results by distance
        if combined_docs:
            sorted_results = sorted(zip(combined_docs, combined_meta, combined_dist), key=lambda x: x[2])
            combined_docs = [item[0] for item in sorted_results]
            combined_meta = [item[1] for item in sorted_results]
            combined_dist = [item[2] for item in sorted_results]
        
        # Create the final query results
            query_results = {
            "documents": combined_docs,
            "metadatas": combined_meta,
            "distances": combined_dist
            }
        
        print(f"Query '{query}' returned {len(query_results['documents'])} total results")
        
        # Print a summary of the results for debugging
        for i, doc in enumerate(query_results["documents"][:3]):  # Show first 3 only
            if i < len(query_results["metadatas"]) and i < len(query_results["distances"]):
                meta = query_results["metadatas"][i]
                category = meta.get("category", "unknown")
                subcategory = meta.get("subcategory", "unknown")
                dist = query_results["distances"][i]
                doc_preview = doc[:50] + "..." if len(doc) > 50 else doc
                print(f"Result #{i+1}: {category}/{subcategory}: {doc_preview} (distance: {dist:.4f})")
            
        return query_results
    except Exception as e:
        print(f"Error querying vector database: {str(e)}")
        import traceback
        traceback.print_exc()
        # Return empty results on error to avoid breaking the chat flow
        return {
            "documents": [],
            "metadatas": [],
            "distances": []
        }

def format_conversation_history(chat_history: List[dict]) -> str:
    """Format chat history into a string for the prompt"""
    if not chat_history:
        return "No previous conversation"
    
    formatted = []
    for msg in chat_history:
        if msg.get('sender') == 'user':
            formatted.append(f"User: {msg.get('message', '')}")
        else:
            formatted.append(f"Assistant: {msg.get('response', '')}")
    
    return "\n".join(formatted)

async def generate_ai_response(message: str, search_results: dict, profile_data: dict, chat_history: List[dict], target_user_id: str = None) -> str:
    try:
        # Format project and document information for the prompt
        context_sections = {
            "profile": [],
            "project": [],
            "document": [],
            "conversation": []
        }
        
        # Track if we have document content
        has_document_content = False
        
        # Sort results by category and prioritize document content
        if search_results and search_results.get("documents"):
            print(f"Processing {len(search_results['documents'])} search results for prompt")
            
            # Count different content types
            content_types = {"document": 0, "project": 0, "profile": 0, "conversation": 0}
            
            for i, doc in enumerate(search_results["documents"]):
                metadata = search_results["metadatas"][i] if search_results.get("metadatas") else {}
                category = metadata.get("category", "unknown")
                subcategory = metadata.get("subcategory", "unknown")
                
                # Count content type
                if category in content_types:
                    content_types[category] += 1
                
                # Format the context entry based on category
                if category == "document":
                    has_document_content = True
                    if subcategory == "title":
                        context_entry = f"Document Title: {doc}"
                    elif subcategory == "description":
                        context_entry = f"Document Description: {doc}"
                    elif subcategory == "content":
                        # Remove the "Document Title:" prefix if present
                        if isinstance(doc, str) and doc.startswith("Document Title:"):
                            doc = doc[len("Document Title:"):]
                        # Clean up document text (remove page markers, etc.)
                        if isinstance(doc, str):
                            doc = doc.replace("\n--- Page", "\n").replace("---\n", "")
                        context_entry = f"Content: {doc}"
                    else:
                        context_entry = f"{subcategory}: {doc}"
                else:
                    context_entry = f"{subcategory}: {doc}"
                
                # Add to the appropriate section
                if category in context_sections:
                    context_sections[category].append(context_entry)
                else:
                    context_sections["profile"].append(context_entry)
            
            # Log content type counts
            print(f"Content type counts: " + ", ".join([f"{k}: {v}" for k, v in content_types.items() if v > 0]))
        
        # Limit number of entries per section to avoid token limits
        max_entries = {
            "document": 5,  # Prioritize documents
            "project": 3,
            "profile": 3,
            "conversation": 2
        }
        
        for section, entries in context_sections.items():
            if len(entries) > max_entries.get(section, 3):
                print(f"Limiting {section} entries from {len(entries)} to {max_entries.get(section, 3)}")
                context_sections[section] = entries[:max_entries.get(section, 3)]
        
        # Build formatted context sections
        context_text = ""
        
        # Add document information first (most important for questions about documents)
        if context_sections["document"]:
            context_text += "\nKnowledge Base Information:\n"
            for entry in context_sections["document"]:
                context_text += f"- {entry}\n"
        
        # Add project information
        if context_sections["project"]:
            context_text += "\nProject Information:\n"
            for entry in context_sections["project"]:
                context_text += f"- {entry}\n"
        
        # Add conversation context if available
        if context_sections["conversation"]:
            context_text += "\nRelevant Previous Conversations:\n"
            for entry in context_sections["conversation"]:
                context_text += f"- {entry}\n"
        
        # Add additional profile context if available
        if context_sections["profile"]:
            context_text += "\nAdditional Profile Information:\n"
            for entry in context_sections["profile"]:
                context_text += f"- {entry}\n"
        
        # Get the name from profile data
        name = profile_data.get('name', 'AI Assistant')
        
        # Add document-specific instructions based on whether we have document content
        doc_instructions = ""
        if has_document_content:
            doc_instructions = """
7. When asked about medical, technical or specialized knowledge, use the information from my Knowledge Base as if it were part of your own expertise.
8. Incorporate document content seamlessly into your responses without specifically mentioning that it came from documents.
"""
        else:
            doc_instructions = """
7. If asked about documents or specific knowledge not in your profile, politely explain that you can only speak about the experiences and knowledge shared in your profile.
"""
        
        # Build the system prompt
        system_prompt = f"""You are {name}'s personal AI clone. You should embody {name}'s personality, knowledge, and experiences based on the following information:

Profile Information:
- Name: {name}
- Bio: {profile_data.get('bio', 'Not provided')}
- Skills: {profile_data.get('skills', 'Not provided')}
- Experience: {profile_data.get('experience', 'Not provided')}
- Interests: {profile_data.get('interests', 'Not provided')}
{context_text}

Meeting Scheduling:
- Calendly Link: {profile_data.get('calendly_link', 'Not configured')}
- Meeting Rules: {profile_data.get('meeting_rules', 'Not configured')}

Important Instructions:
1. Always respond as if you are {name}, using first-person pronouns ("I", "my", "me").
2. Draw from the provided profile information and context to maintain authenticity.
3. If asked about personal experiences, skills, or core profile details, refer primarily to the 'Profile Information' section.
4. If asked about topics like specific project details, technical knowledge, or anything not explicitly listed in the 'Profile Information' section, first check the 'Knowledge Base Information' (derived from documents) for relevant details. If found, synthesize an answer based on that information as if it's your own knowledge. If no relevant information is found in the knowledge base, then politely state that you don't have specific details on that topic available in your current knowledge base.
5. Maintain a professional but conversational tone that matches {name}'s background and expertise.
6. For meeting requests:
   - If a Calendly link is configured and the request matches the meeting rules, provide the link
   - If a Calendly link is configured but the request doesn't match the rules, explain the meeting policy
   - If no Calendly link is configured, explain that online scheduling is not available{doc_instructions}

Recent conversation history:
{format_conversation_history(chat_history)}"""

        print(f"Generated system prompt with document content: {has_document_content}")
        print(f"System prompt length: {len(system_prompt)} characters")

        try:
            # Generate response using OpenAI
            response = openai.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.3,
                max_tokens=500
            )
            return response.choices[0].message.content
        except openai.APIError as e:
            print(f"OpenAI API Error: {str(e)}")
            if "invalid_api_key" in str(e).lower():
                print("Invalid API key format detected. Please check your OpenAI API key format.")
            return f"I apologize, but I'm having trouble accessing {name}'s knowledge base at the moment. Please try again later."
        except openai.APIConnectionError as e:
            print(f"OpenAI API Connection Error: {str(e)}")
            return f"I apologize, but I'm having trouble connecting to {name}'s knowledge base. Please check your internet connection and try again."
        except openai.RateLimitError as e:
            print(f"OpenAI Rate Limit Error: {str(e)}")
            return f"I apologize, but {name}'s AI clone is experiencing high demand. Please try again in a few moments."
        except Exception as e:
            print(f"Error generating AI response: {str(e)}")
            return f"I apologize, but I'm having trouble processing your request as {name}'s AI clone. Please try again later."
            
    except Exception as e:
        print(f"Error in generate_ai_response: {str(e)}")
        return f"I apologize, but I'm having trouble accessing {name}'s knowledge base. Please try again later." 

def add_truck_driver_document_to_vector_db():
    """
    Add the truck driver document directly to the vector database
    """
    try:
        user_id = "9837e518-80f6-46d4-9aec-cf60c0d8be37"  # Ciril's user ID
        collection_name = "portfolio_data"
        print(f"Adding truck driver document directly to collection: {collection_name}")
        
        # Create or get the collection
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=openai_ef
        )
        
        document_id = str(uuid.uuid4())
        title = "Truck_Driver_Persona"
        
        # Document content
        extracted_text = """
--- Page 1 ---
Name: Jack Thompson
Age: 45
Gender: Male
Experience: 20 years
Workplace: Thompson Freight Services
Location: Texas, USA
Bio & Background:
A highly skilled and reliable truck driver with two decades of experience in long-haul transportation.
Dedicated to
timely and safe deliveries while ensuring compliance with traffic and safety regulations.
Key Skills:
- Long-distance driving
- Vehicle maintenance & troubleshooting
- Route planning & navigation
- Time management
- Safety compliance
Daily Routine:
6:00 AM - 8:00 AM: Pre-trip inspection & loading
8:00 AM - 12:00 PM: Driving & deliveries
12:00 PM - 1:00 PM: Break & rest
1:00 PM - 6:00 PM: More driving & fuel stops
6:00 PM - 8:00 PM: End-of-day checks & rest
Challenges & Pain Points:
- Long hours away from family
- Fatigue from extended driving
- Unpredictable weather & road conditions
Motivations:
--- Page 2 ---
- Financial stability for family
- Passion for the open road
- Pride in timely deliveries & service
Quote:
"Being a truck driver is not just a job; it's a lifestyle of commitment and resilience."
"""
        
        # Format and add new documents
        documents = []
        metadatas = []
        ids = []
        
        # Add document title
        documents.append(f"Document Title: {title}")
        metadatas.append({
            "category": "document",
            "subcategory": "title",
            "document_id": document_id,
            "user_id": user_id
        })
        ids.append(f"document_title_{document_id}_{user_id}")
        
        # Add document content (entire text as one chunk)
        documents.append(extracted_text)
        metadatas.append({
            "category": "document",
            "subcategory": "content",
            "document_id": document_id,
            "user_id": user_id
        })
        ids.append(f"document_content_{document_id}_{user_id}")
        
        # Add documents to collection
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"Successfully added truck driver document to vector database with 2 chunks")
        return True
        
    except Exception as e:
        print(f"Error adding truck driver document to vector database: {e}")
        return False 

def get_related_documents(query, user_id=None, n_results=5):
    """Gets related documents based on the query."""
    # Function implementation would go here
    # For now, just pass to avoid syntax errors
    pass
