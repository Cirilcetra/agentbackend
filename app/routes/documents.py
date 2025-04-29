from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Body
# Import the shared Supabase client
from app.database import supabase 
from app.auth import get_current_user, User
from typing import Optional, Dict, Any
import logging
import os
import io
import pdfplumber
# Remove local Supabase client import
# from supabase import create_client
from app.embeddings import add_document_to_vector_db
import time
import chromadb
from pydantic import BaseModel

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Remove local Supabase client initialization
# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# supabase = None
# 
# try:
#     if SUPABASE_URL and SUPABASE_KEY:
#         supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
#         logger.info("Supabase client initialized in document routes")
#     else:
#         logger.warning("Missing Supabase environment variables in document routes")
# except Exception as e:
#     logger.error(f"Error initializing Supabase client: {e}")

# Initialize ChromaDB client connection - reuse the same connection as in embeddings.py
from app.embeddings import chroma_client, openai_ef

@router.post("/process", status_code=status.HTTP_200_OK)
async def process_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    filePath: str = Form(...),
    userId: str = Form(...),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Process a PDF document and extract its text content using pdfplumber
    """
    try:
        logger.info(f"Processing document: {title} (userId: {userId}, filePath: {filePath})")
        
        # Validate user authorization
        if current_user.id != userId:
            logger.warning(f"Authorization mismatch: user {current_user.id} tried to process document for user {userId}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to process documents for this user"
            )
        
        # Verify file is a PDF
        if not file.content_type or not file.content_type.startswith("application/pdf"):
            logger.warning(f"Invalid file type: {file.content_type}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported"
            )
        
        # Read file content
        content = await file.read()
        logger.info(f"Read {len(content)} bytes from uploaded file")
        
        if len(content) == 0:
            logger.warning("Empty file uploaded")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )
        
        # Extract text from PDF using pdfplumber
        extracted_text = ""
        page_count = 0
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                page_count = len(pdf.pages)
                logger.info(f"PDF has {page_count} pages")
                
                # Extract text from each page
                for page_num, page in enumerate(pdf.pages):
                    logger.info(f"Processing page {page_num + 1}")
                    page_text = page.extract_text()
                    if page_text:
                        extracted_text += f"\n--- Page {page_num + 1} ---\n"
                        extracted_text += page_text
                    else:
                        logger.warning(f"No text extracted from page {page_num + 1}")
                
                logger.info(f"Successfully extracted text from {page_count} pages")
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to extract text from PDF: {str(e)}"
            )
        
        # Check if any text was extracted
        if not extracted_text:
            logger.warning("No text extracted from the document")
            extracted_text = "No text could be extracted from this document."
            
        # Generate a temporary document ID for vector DB
        temp_id = f"temp_{userId}_{int(time.time())}"
        
        # Create document data structure for vector DB
        document_data = {
            "id": temp_id,
            "title": title,
            "description": description,
            "file_name": file.filename,
            "extracted_text": extracted_text,
            "storage_path": filePath
        }
        
        # Add the document to the vector database for chatbot context
        logger.info(f"Adding document to vector database for user: {userId} with title: {title}")
        logger.info(f"Extracted text length: {len(extracted_text)} characters")
        vector_db_success = add_document_to_vector_db(document_data, userId)
        
        if vector_db_success:
            logger.info(f"Successfully added document to vector database with temp_id: {temp_id}")
            
            # Test query to ensure document is searchable
            try:
                from app.embeddings import query_vector_db
                test_query = f"content from {title}"
                logger.info(f"Testing document searchability with query: '{test_query}'")
                test_results = query_vector_db(test_query, n_results=3, user_id=userId)
                doc_found = False
                
                if test_results and test_results.get("documents"):
                    for i, doc in enumerate(test_results.get("documents", [])):
                        meta = test_results.get("metadatas", [])[i] if test_results.get("metadatas") else {}
                        if meta.get("category") == "document" and meta.get("document_id") == temp_id:
                            doc_found = True
                            logger.info(f"Document found in test query: {meta.get('subcategory')}")
                
                if not doc_found:
                    logger.warning(f"Document was added but not found in test query - check embedding process")
            except Exception as test_error:
                logger.error(f"Error testing document searchability: {str(test_error)}")
        else:
            logger.warning("Failed to add document to vector database, but continuing with processing")
        
        # Return extracted text
        logger.info(f"Document processing complete: extracted {len(extracted_text)} characters")
        return {
            "status": "success",
            "message": "Document processed successfully",
            "extracted_text": extracted_text,
            "num_pages": page_count,
            "vector_db_indexed": vector_db_success,
            "temp_id": temp_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )

class UpdateVectorDBRequest(BaseModel):
    temp_id: str
    permanent_id: str
    user_id: str

@router.post("/update-vector-db", status_code=status.HTTP_200_OK)
async def update_vector_db(
    data: UpdateVectorDBRequest = Body(...),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Update the document ID in the vector database after saving to Supabase
    """
    try:
        # Validate user authorization
        if current_user.id != data.user_id:
            logger.warning(f"Authorization mismatch: user {current_user.id} tried to update document for user {data.user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to update documents for this user"
            )
            
        logger.info(f"Updating document ID in vector DB: {data.temp_id} -> {data.permanent_id}")
        
        # Get the collection
        collection_name = "portfolio_data"
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=openai_ef
        )
        
        # Find all document chunks with the temporary ID
        try:
            # Get the IDs of documents with this temp ID
            logger.info(f"Querying for documents with temp_id: {data.temp_id} and user_id: {data.user_id}")
            get_ids_response = collection.get(
                where={
                    "$and": [
                        {"document_id": {"$eq": data.temp_id}},
                        {"user_id": {"$eq": data.user_id}}
                    ]
                }
            )
            
            document_ids = get_ids_response.get("ids", [])
            if not document_ids or len(document_ids) == 0:
                logger.warning(f"No documents found with temp ID: {data.temp_id}")
                
                # Try a direct query without filtering to see what's available
                logger.info("Performing diagnostic query to find what documents exist")
                try:
                    all_docs = collection.get(
                        where={"user_id": {"$eq": data.user_id}}
                    )
                    logger.info(f"Found {len(all_docs.get('ids', []))} total documents for user {data.user_id}")
                    for i, doc_id in enumerate(all_docs.get('ids', [])[:5]):  # Show first 5 only
                        logger.info(f"Sample document {i}: {doc_id}")
                except Exception as diag_error:
                    logger.error(f"Diagnostic query failed: {diag_error}")
                
                return {
                    "status": "warning",
                    "message": "No documents found to update",
                    "updated": 0
                }
                
            logger.info(f"Found {len(document_ids)} document chunks to update")
            
            # Update the document IDs
            updated_ids = []
            for old_id in document_ids:
                # Create new ID by replacing the temp ID with the permanent ID
                if "document_title_" in old_id:
                    new_id = f"document_title_{data.permanent_id}_{data.user_id}"
                elif "document_description_" in old_id:
                    new_id = f"document_description_{data.permanent_id}_{data.user_id}"
                elif "_content_" in old_id:
                    # Extract the chunk index if present
                    parts = old_id.split("_")
                    if len(parts) >= 4 and parts[-2].isdigit():  # Format: document_content_id_index_user_id
                        chunk_index = parts[-2]
                        new_id = f"document_content_{data.permanent_id}_{chunk_index}_{data.user_id}"
                    else:  # Format: document_content_id_user_id
                        new_id = f"document_content_{data.permanent_id}_{data.user_id}"
                else:
                    # Default fallback - replace temp ID with permanent ID but keep user_id
                    new_id = old_id.replace(data.temp_id, data.permanent_id)
                
                # Ensure ID is unique by adding sequence number if needed
                base_id = new_id
                counter = 0
                while new_id in updated_ids:
                    counter += 1
                    new_id = f"{base_id}_{counter}"
                    
                updated_ids.append(new_id)
                logger.info(f"ID mapping: {old_id} -> {new_id}")
            
            # Get the documents to update
            documents = get_ids_response.get("documents", [])
            metadatas = get_ids_response.get("metadatas", [])
            embeddings = get_ids_response.get("embeddings", [])
            
            # Update the document_id in all metadatas
            for i in range(len(metadatas)):
                if metadatas[i] and "document_id" in metadatas[i]:
                    metadatas[i]["document_id"] = data.permanent_id
            
            # Delete the old documents
            collection.delete(ids=document_ids)
            
            # Add the updated documents
            collection.add(
                ids=updated_ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings
            )
            
            logger.info(f"Successfully updated {len(updated_ids)} document chunks in vector DB")
            
            return {
                "status": "success",
                "message": "Document IDs updated in vector database",
                "updated": len(updated_ids)
            }
            
        except Exception as e:
            logger.error(f"Error updating document IDs in vector DB: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error updating document IDs: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating document IDs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        ) 