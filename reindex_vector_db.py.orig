#!/usr/bin/env python3
import os
import sys
import logging
import time
from dotenv import load_dotenv
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"reindex_documents.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import database and embedding functions
try:
    from app.database import get_all_profiles, get_all_documents
    from app.embeddings import add_profile_to_vector_db, add_document_to_vector_db, add_projects_to_vector_db, chroma_client
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)

def reindex_profiles():
    """Reindex all user profiles in the vector database"""
    logger.info("Starting profile reindexing...")
    try:
        # Get all profiles from the database
        profiles = get_all_profiles()
        logger.info(f"Retrieved {len(profiles)} profiles to reindex")
        
        success_count = 0
        error_count = 0
        
        for profile in profiles:
            try:
                user_id = profile.get("user_id")
                if user_id:
                    logger.info(f"Reindexing profile for user {user_id}")
                    result = add_profile_to_vector_db(profile, user_id)
                    if result:
                        success_count += 1
                        logger.info(f"Successfully reindexed profile for user {user_id}")
                    else:
                        error_count += 1
                        logger.error(f"Failed to reindex profile for user {user_id}")
                else:
                    logger.warning(f"Skipping profile without user_id: {profile.get('id')}")
            except Exception as e:
                error_count += 1
                logger.error(f"Error reindexing profile: {e}")
        
        logger.info(f"Profile reindexing complete. Success: {success_count}, Errors: {error_count}")
        return success_count, error_count
    
    except Exception as e:
        logger.error(f"Error during profile reindexing: {e}")
        return 0, 0

def reindex_projects_from_table():
    """Reindex all projects from the projects table in the vector database"""
    logger.info("Starting projects table reindexing...")
    try:
        # Get all projects from the database
        from app.database import get_all_projects_from_table
        projects = get_all_projects_from_table()
        logger.info(f"Retrieved {len(projects)} projects from projects table to reindex")
        
        success_count = 0
        error_count = 0
        user_projects = {}
        
        # Group projects by user_id
        for project in projects:
            user_id = project.get("user_id")
            if not user_id:
                logger.warning(f"Skipping project without user_id: {project.get('id')}")
                continue
                
            if user_id not in user_projects:
                user_projects[user_id] = []
            
            user_projects[user_id].append(project)
        
        # Process each user's projects
        for user_id, projects_list in user_projects.items():
            try:
                logger.info(f"Adding {len(projects_list)} projects for user_id: {user_id}")
                result = add_projects_to_vector_db(projects_list, user_id)
                if result:
                    success_count += 1
                    logger.info(f"Successfully added projects for user_id: {user_id}")
                else:
                    error_count += 1
                    logger.error(f"Failed to add projects for user_id: {user_id}")
            except Exception as e:
                error_count += 1
                logger.error(f"Error adding projects for user_id {user_id}: {e}")
        
        logger.info(f"Projects reindexing complete. Success: {success_count}, Errors: {error_count}")
        return success_count, error_count
    
    except Exception as e:
        logger.error(f"Error during projects reindexing: {e}")
        return 0, 0

def reindex_documents():
    """Reindex all documents in the vector database"""
    logger.info("Starting document reindexing...")
    try:
        # Get all documents from the database
        documents = get_all_documents()
        logger.info(f"Retrieved {len(documents)} documents to reindex")
        
        success_count = 0
        error_count = 0
        
        for doc in documents:
            try:
                user_id = doc.get("user_id")
                if not user_id:
                    logger.warning(f"Skipping document without user_id: {doc.get('id')}")
                    continue
                
                # Format document data for vector DB
                document_data = {
                    "id": doc.get("id"),
                    "title": doc.get("title"),
                    "description": doc.get("description"),
                    "file_name": doc.get("file_name"),
                    "extracted_text": doc.get("extracted_text"),
                    "storage_path": doc.get("storage_path")
                }
                
                logger.info(f"Reindexing document {doc.get('id')} for user {user_id}")
                
                if document_data.get("extracted_text"):
                    result = add_document_to_vector_db(document_data, user_id)
                    if result:
                        success_count += 1
                        logger.info(f"Successfully reindexed document {doc.get('id')}")
                    else:
                        error_count += 1
                        logger.error(f"Failed to reindex document {doc.get('id')}")
                else:
                    logger.warning(f"Skipping document without extracted text: {doc.get('id')}")
            except Exception as e:
                error_count += 1
                logger.error(f"Error reindexing document {doc.get('id', 'unknown')}: {e}")
        
        logger.info(f"Document reindexing complete. Success: {success_count}, Errors: {error_count}")
        return success_count, error_count
    
    except Exception as e:
        logger.error(f"Error during document reindexing: {e}")
        return 0, 0

def clear_vector_db():
    """Clear all data in the vector database"""
    logger.info("Clearing vector database...")
    try:
        # Get the collection
        collection_name = "portfolio_data"
        try:
            collection = chroma_client.get_collection(name=collection_name)
            
            # Count items before deletion
            count = collection.count()
            logger.info(f"Vector database contains {count} items before clearing")
            
            if count > 0:
                # Get all IDs in the collection
                all_ids = collection.get()["ids"]
                if all_ids:
                    # Delete all items using the IDs
                    collection.delete(ids=all_ids)
                    logger.info(f"Cleared all {len(all_ids)} items from {collection_name} collection")
                else:
                    logger.info(f"No items found in collection to delete")
            else:
                logger.info(f"Collection is empty, nothing to delete")
            
            # Reset the collection
            from app.embeddings import openai_ef
            
            # Delete and recreate the collection
            chroma_client.delete_collection(name=collection_name)
            collection = chroma_client.create_collection(
                name=collection_name,
                embedding_function=openai_ef
            )
            
            logger.info(f"Recreated empty collection {collection_name}")
            
            return True
        except Exception as e:
            logger.error(f"Error clearing vector database: {e}")
            return False
    except Exception as e:
        logger.error(f"Error accessing vector database: {e}")
        return False

if __name__ == "__main__":
    start_time = time.time()
    logger.info("=== Starting vector database reindexing ===")
    
    # Ask for confirmation
    if len(sys.argv) < 2 or sys.argv[1] != "--force":
        confirm = input("This will clear and rebuild the vector database. Are you sure? (yes/no): ")
        if confirm.lower() != "yes":
            logger.info("Reindexing cancelled by user")
            sys.exit(0)
    
    # Clear the vector database
    clear_result = clear_vector_db()
    if not clear_result:
        logger.warning("Failed to clear vector database, proceeding with reindexing anyway")
    
    # Reindex profiles
    profile_success, profile_errors = reindex_profiles()
    
    # Reindex projects directly from projects table
    projects_success, projects_errors = reindex_projects_from_table()
    
    # Reindex documents
    doc_success, doc_errors = reindex_documents()
    
    # Calculate completion time
    end_time = time.time()
    duration = end_time - start_time
    
    # Log summary
    logger.info("=== Reindexing completed ===")
    logger.info(f"Total duration: {duration:.2f} seconds")
    logger.info(f"Profiles reindexed: {profile_success} success, {profile_errors} errors")
    logger.info(f"Projects reindexed: {projects_success} success, {projects_errors} errors")
    logger.info(f"Documents reindexed: {doc_success} success, {doc_errors} errors")
    
    print(f"Reindexing completed in {duration:.2f} seconds")
    print(f"Profiles: {profile_success} success, {profile_errors} errors")
    print(f"Projects: {projects_success} success, {projects_errors} errors")
    print(f"Documents: {doc_success} success, {doc_errors} errors") 