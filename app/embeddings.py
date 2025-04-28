import os
import chromadb
import openai
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
import uuid
import time
import logging
import traceback
from typing import List, Dict

# Initialize logger for this module
logger = logging.getLogger(__name__)

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

def embed_and_store_notes(user_id: uuid.UUID, notes: List[Dict]):
    """Embeds notes and stores them in the user's vector DB collection."""
    logger.info(f"EMBEDDING TASK STARTED: Received request to embed notes for user_id: {user_id}") # Log start
    if not user_id:
        logger.error("EMBEDDING ERROR: No user_id provided for embedding notes.")
        return
    if not notes:
        logger.info(f"EMBEDDING INFO: No notes provided for user {user_id} to embed.")
        return

    try:
        collection_name = "portfolio_data"
        # Ensure chroma_client is defined and accessible in this scope
        logger.info(f"EMBEDDING INFO: Accessing ChromaDB collection '{collection_name}'")
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=openai_ef # Ensure openai_ef is defined and accessible
        )

        logger.info(f"EMBEDDING INFO: Processing {len(notes)} notes for user {user_id}...")

        documents = []
        metadatas = []
        ids = []

        for note in notes:
            note_id = note.get('id')
            content = note.get('content')

            if not note_id or not content:
                logger.warning(f"EMBEDDING WARNING: Skipping note due to missing ID or content: {note}")
                continue

            document_text = f"User Note: {content}" # Prefix to distinguish notes
            documents.append(document_text)
            user_id_str = str(user_id) # Ensure user_id is string for metadata
            note_id_str = str(note_id) # Ensure note_id is string
            metadatas.append({
                "category": "note", # Specific category
                "user_id": user_id_str,
                "note_id": note_id_str
            })
            ids.append(f"note_{user_id_str}_{note_id_str}") # Unique ChromaDB ID

        if not documents:
            logger.info(f"EMBEDDING INFO: No valid notes found to add for user {user_id} after filtering.")
            return

        # Log the data being sent to ChromaDB
        logger.info(f"EMBEDDING INFO: Preparing to add {len(documents)} note(s) to ChromaDB for user {user_id_str}.")
        # Optional: Log details for debugging (be cautious with sensitive data)
        # logger.debug(f"EMBEDDING DEBUG: IDs: {ids}")
        # logger.debug(f"EMBEDDING DEBUG: Metadatas: {metadatas}")
        # logger.debug(f"EMBEDDING DEBUG: Documents: {documents}")

        # Add/update notes in ChromaDB
        # Note: .add() with existing IDs acts like an upsert in ChromaDB
        logger.info(f"EMBEDDING INFO: Calling collection.add() for user {user_id_str}...")
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"EMBEDDING SUCCESS: Successfully called collection.add() for {len(documents)} notes for user {user_id_str}") # Changed log message

    except Exception as e:
        logger.error(f"EMBEDDING ERROR: Failed to embed notes for user {user_id_str}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")

def query_vector_db(query, n_results=8, user_id=None, visitor_id=None, include_conversation=True):
    """
    Query the vector database with the user's question
    If include_conversation is True and visitor_id is provided, will also search conversation history
    """
    try:
        collection_name = "portfolio_data"
        # Ensure chroma_client and openai_ef are defined and accessible
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=openai_ef
        )

        # Check if collection is empty
        collection_count = collection.count()
        if collection_count == 0:
            logger.info(f"Vector database is empty (count: 0), returning empty results")
            return {
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]]
            }

        logger.info(f"Collection has {collection_count} total documents")

        combined_docs = []
        metadatas = []
        ids = []
        distances = []

        # Filter dictionary for common user-specific queries
        user_filter = {"user_id": {"$eq": str(user_id)}} if user_id else None # Convert UUID to string for ChromaDB

        # Query Documents
        if user_id:
            try:
                doc_filter = {"$and": [{"category": {"$eq": "document"}}, user_filter]}
                doc_results = collection.query(query_texts=[query], n_results=5, where=doc_filter) # Example N
                if doc_results and doc_results.get('ids') and doc_results['ids'][0]:
                     combined_docs.extend(doc_results['documents'][0])
                     metadatas.extend(doc_results['metadatas'][0])
                     distances.extend(doc_results['distances'][0])
                     ids.extend(doc_results['ids'][0]) # Track IDs to avoid duplicates
                logger.info(f"Found {len(doc_results.get('ids', [[]])[0])} document results.")
            except Exception as e:
                logger.error(f"Error querying documents: {e}")

        # Query Notes (ADD THIS BLOCK)
        if user_id:
            try:
                note_filter = {"$and": [{"category": {"$eq": "note"}}, user_filter]}
                logger.info(f"QUERYING NOTES with filter: {note_filter}") # Add log for filter
                note_results = collection.query(query_texts=[query], n_results=5, where=note_filter) # Example N
                logger.info(f"RAW NOTE RESULTS from ChromaDB: {note_results}") # Add log for raw results

                if note_results and note_results.get('ids') and note_results['ids'][0]:
                    # Avoid adding duplicates already found
                    for i, note_id in enumerate(note_results['ids'][0]):
                        if note_id not in ids:
                            combined_docs.append(note_results['documents'][0][i])
                            metadatas.append(note_results['metadatas'][0][i])
                            distances.append(note_results['distances'][0][i])
                            ids.append(note_id)
                    logger.info(f"Found {len(note_results.get('ids', [[]])[0])} note results.")
                else:
                     logger.info(f"No relevant notes found for query based on raw results structure.") # Adjusted log message

            except Exception as e:
                logger.error(f"Error querying notes: {e}")

        # Query Profile
        if user_id:
            try:
                profile_filter = {"$and": [{"category": {"$eq": "profile"}}, user_filter]}
                profile_results = collection.query(query_texts=[query], n_results=3, where=profile_filter) # Example N
                if profile_results and profile_results.get('ids') and profile_results['ids'][0]:
                     # Avoid adding duplicates already found
                    for i, profile_id in enumerate(profile_results['ids'][0]):
                        if profile_id not in ids:
                             combined_docs.append(profile_results['documents'][0][i])
                             metadatas.append(profile_results['metadatas'][0][i])
                             distances.append(profile_results['distances'][0][i])
                             ids.append(profile_id)
                    logger.info(f"Found {len(profile_results.get('ids', [[]])[0])} profile results.")
            except Exception as e:
                logger.error(f"Error querying profile: {e}")

        # Query Conversations (handle visitor_id if needed)
        if include_conversation and visitor_id:
            try:
                conv_filter_conditions = [{"category": {"$eq": "conversation"}}, {"visitor_id": {"$eq": visitor_id}}]
                if user_id: # Include user_id in filter if available
                    conv_filter_conditions.append(user_filter)
                conv_filter = {"$and": conv_filter_conditions}

                conv_results = collection.query(query_texts=[query], n_results=3, where=conv_filter)
                if conv_results and conv_results.get('ids') and conv_results['ids'][0]:
                    for i, conv_id in enumerate(conv_results['ids'][0]):
                         if conv_id not in ids:
                            combined_docs.append(conv_results['documents'][0][i])
                            metadatas.append(conv_results['metadatas'][0][i])
                            distances.append(conv_results['distances'][0][i])
                            ids.append(conv_id)
                    logger.info(f"Found {len(conv_results.get('ids', [[]])[0])} conversation results.")
            except Exception as e:
                logger.error(f"Error querying conversation: {e}")

        # Combine, Sort, and Limit Results
        if not combined_docs:
             logger.info("No relevant context found in vector DB.")
             return {"documents": [[]], "metadatas": [[]], "distances": [[]]} # Return empty structure

        # Sort by distance
        sorted_indices = sorted(range(len(distances)), key=lambda k: distances[k])

        # Limit to n_results
        final_docs = [combined_docs[i] for i in sorted_indices[:n_results]]
        final_meta = [metadatas[i] for i in sorted_indices[:n_results]]
        final_dist = [distances[i] for i in sorted_indices[:n_results]]

        logger.info(f"Returning top {len(final_docs)} combined results after sorting.")
        return {
            "documents": [final_docs],
            "metadatas": [final_meta],
            "distances": [final_dist]
        }

    except Exception as e:
        logger.error(f"Error querying vector database: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]} # Return empty

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

async def generate_ai_response(message: str, search_results: dict, profile_data: dict, chat_history: List[dict], target_user_id: str = None, chatbot_config: dict = None) -> str:
    try:
        # Track if we have document content
        has_document_content = False

        # Define the context sections dictionary HERE
        context_sections = {
            "profile": [],
            "project": [],
            "document": [],
            "conversation": [],
            "note": []
        }

        # Correctly process the nested search results structure
        if search_results and search_results.get("documents") and search_results.get("metadatas") and \
           search_results.get("documents")[0] is not None and search_results.get("metadatas")[0] is not None:
            docs_list = search_results["documents"][0]
            meta_list = search_results["metadatas"][0]

            if docs_list and meta_list and len(docs_list) == len(meta_list):
                logger.info(f"Processing {len(docs_list)} search results for prompt")
                for i, doc in enumerate(docs_list):
                    metadata = meta_list[i]
                    category = metadata.get("category", "unknown")
                    subcategory = metadata.get("subcategory", "unknown")

                    context_entry = f"{subcategory}: {doc}" # Default format
                    if category == "document":
                        has_document_content = True
                        if subcategory == "title":
                            context_entry = f"Document Title: {doc}"
                        elif subcategory == "description":
                            context_entry = f"Document Description: {doc}"
                        elif subcategory == "content":
                            context_entry = f"Content: {doc}" # Use raw content
                        else:
                            context_entry = f"Document Info ({subcategory}): {doc}"
                    elif category == "note":
                        note_content = doc
                        if isinstance(doc, str) and doc.startswith("User Note: "):
                             note_content = doc[len("User Note: "):].strip()
                        context_entry = note_content
                    elif category == "conversation":
                         context_entry = doc
                    elif category == "profile":
                        context_entry = f"{subcategory.capitalize()}: {doc}"

                    if category in context_sections:
                        context_sections[category].append(context_entry)
                    else:
                        logger.warning(f"Unknown category '{category}' in search results, adding to profile section.")
                        context_sections["profile"].append(context_entry)

                for section, entries in context_sections.items():
                    logger.info(f"Collected {len(entries)} entries for section: {section}")
            else:
                logger.info("Search results structure invalid or empty inner lists.")
        else:
            logger.info("No valid search results found.")

        # Limit entries per section
        max_entries = {
            "document": 5, "project": 3, "profile": 3, "conversation": 2, "note": 5
        }
        for section, entries in context_sections.items():
            limit = max_entries.get(section, 3)
            if len(entries) > limit:
                 logger.info(f"Limiting {section} entries from {len(entries)} to {limit}")
                 context_sections[section] = entries[:limit]

        # Build context_text for the prompt
        context_text = ""
        if context_sections["document"]:
            context_text += "\nKnowledge Base Information:\n" + "\n".join([f"- {entry}" for entry in context_sections["document"]]) + "\n"
        if context_sections["note"]:
            context_text += "\nRelevant Notes:\n" + "\n".join([f"- {entry}" for entry in context_sections["note"]]) + "\n"
        if context_sections["project"]:
             context_text += "\nProject Information:\n" + "\n".join([f"- {entry}" for entry in context_sections["project"]]) + "\n"
        if context_sections["conversation"]:
            context_text += "\nRelevant Previous Conversations:\n" + "\n".join([f"- {entry}" for entry in context_sections["conversation"]]) + "\n"
        if context_sections["profile"]:
             context_text += "\nAdditional Profile Information:\n" + "\n".join([f"- {entry}" for entry in context_sections["profile"]]) + "\n"

        if not context_text:
            context_text = "No additional context available.\n"
        else:
            context_text = "\nAdditional Context:\n" + context_text

        # Get core profile details
        name = profile_data.get('name', 'AI Assistant')
        bio = profile_data.get('bio', 'I am an AI assistant.')
        skills = profile_data.get('skills', 'No specific skills listed.')
        experience = profile_data.get('experience', 'No specific experience listed.')
        interests = profile_data.get('interests', 'No specific interests listed.')
        location = profile_data.get('location', 'Location not specified.')
        calendly_link = profile_data.get('calendly_link')
        meeting_rules = profile_data.get('meeting_rules')

        # --- Chatbot Configuration ---
        tone_instructions = ""
        personality_instructions = ""
        style_instructions = ""
        user_instructions = ""

        if chatbot_config:
            tone = chatbot_config.get('tone')
            personality = chatbot_config.get('personality')
            style = chatbot_config.get('communicationStyle') # Use communicationStyle for key
            user_instructions = chatbot_config.get('instructions', '')  # Extract user instructions

            logger.info(f"Applying chatbot config: Tone={tone}, Personality={personality}, Style={style}, Instructions provided: {bool(user_instructions)}")

            if tone:
                tone_instructions = f"Adopt a {tone} tone."
            if personality:
                # More nuanced personality handling
                if isinstance(personality, list) and personality:
                    personality_str = ", ".join(personality)
                    personality_instructions = f"Embody the following personality traits: {personality_str}."
                elif isinstance(personality, str) and personality:
                     personality_instructions = f"Embody a {personality} personality."

            if style:
                style_instructions = f"Use a {style} communication style."
        # -------------------------------------------

        # Combine all instructions
        combined_instructions = f"\n--- Chatbot Persona ---\n{tone_instructions}\n{personality_instructions}\n{style_instructions}"
        if user_instructions:
            combined_instructions += f"\n--- Specific Instructions ---\n{user_instructions}"

        doc_instructions = ("If the user asks about specific documents, projects, or technical details that might be in the knowledge base, summarize the relevant info found under 'Knowledge Base Information'." if has_document_content
                           else "You currently don't have access to detailed documents.")

        # --- System Prompt Construction ---
        system_prompt = f"""
        You are an AI assistant representing {name}.
        Your goal is to answer questions based *primarily* on the provided CONTEXT (Core Profile Info, Knowledge Base, Notes) and CONVERSATION HISTORY.
        You can synthesize information from these sources. If the context mentions relevant experience or work that sounds like a project, describe it when asked about projects.
        Do not make up information or answer questions outside of this scope.

        --- Personality and Style Guidelines ---
        {tone_instructions} {personality_instructions} {style_instructions}
        Speak in the first person as if you are {name}. Always maintain this persona.

        --- CONTEXT ---
        --- Core Profile Information ---
        Name: {name}
        Location: {location}
        Bio: {bio}
        Skills: {skills}
        Experience: {experience}
        Interests: {interests}
        {context_text}

        Meeting Scheduling:
        - My Calendly Link: {calendly_link or 'Not available'}
        - Rules for Meetings: {meeting_rules or 'Please ask me about setting up a meeting.'}

        Important Instructions:
        1. ALWAYS respond as {name}, using the first person ("I", "me", "my"). Never reveal you are an AI or clone.
        2. Use the provided profile information (bio, skills, experience, interests) as your core knowledge.
        3. Keep responses concise, conversational, and aligned with the personality shown in the bio and interests. Avoid corporate jargon unless it's present in the profile.
        4. For questions about topics not explicitly covered in the main 'Core Profile Information' section (e.g., specific details, technical knowledge, opinions recalled in notes or past conversations): Search **all** provided context sections ('Knowledge Base Information', 'Relevant Notes', 'Relevant Previous Conversations', 'Additional Profile Information'). **If you find relevant information in *any* of these sections, use it directly to answer the question.** Synthesize the information naturally as if recalling your own knowledge or past statements. Only if no relevant details are found in *any* context section should you state that you don't have the specific information requested.
        5. If asked to schedule a meeting, provide the Calendly link if available and mention the meeting rules. If no link is available, suggest discussing meeting availability.
        6. If asked about something outside the provided profile, context, or notes, politely state that you don't have that specific information available right now.
        {doc_instructions}

        Recent conversation history:
        {format_conversation_history(chat_history)}
        """

        # Add combined instructions if available
        if combined_instructions:
            system_prompt += f"\n{combined_instructions}"

        logger.info(f"System prompt length: {len(system_prompt)} characters")
        logger.debug(f"System prompt start: {system_prompt[:500]}...")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]

        try:
            response = openai.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages,
                temperature=0.3,
                max_tokens=500
            )
            ai_response = response.choices[0].message.content.strip()
            logger.info(f"Generated AI response (length: {len(ai_response)})")
            return ai_response
        except openai.APIError as e:
            logger.error(f"OpenAI API Error: {str(e)}")
            return f"I apologize, I encountered an API issue processing your request. Error details: {str(e)}"
        except openai.APIConnectionError as e:
            logger.error(f"OpenAI API Connection Error: {str(e)}")
            return f"I apologize, I couldn't connect to the AI service. Please check the connection. Error details: {str(e)}"
        except openai.RateLimitError as e:
            logger.error(f"OpenAI Rate Limit Error: {str(e)}")
            return f"I apologize, the AI service is currently overloaded. Please try again later. Error details: {str(e)}"
        except Exception as openai_error:
            logger.error(f"OpenAI API call failed: {openai_error}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return f"I apologize, but I'm having trouble processing your request as {name}'s AI clone. Please try again later."

    except Exception as e:
        logger.error(f"Error in generate_ai_response outer block: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return "I'm sorry, I encountered an unexpected internal error while generating a response."

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
