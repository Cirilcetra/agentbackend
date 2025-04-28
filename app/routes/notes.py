# backend/app/routes/notes.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List
import uuid
import logging
import traceback

# Ensure these models and functions are correctly imported from your project structure
from app.models import NoteCreate, NoteRead
from app.database import get_notes, create_note
from app.auth import get_current_user, User
from app.embeddings import embed_and_store_notes # Make sure this path is correct

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/notes",
    tags=["Notes"],
)

@router.get("", response_model=List[NoteRead])
async def read_user_notes(
    current_user: User = Depends(get_current_user)
):
    """Retrieve all notes for the currently authenticated user."""
    try:
        user_id_uuid = uuid.UUID(current_user.id)
        logger.info(f"Fetching notes for authenticated user: {current_user.id}")
        notes_data = get_notes(user_id=user_id_uuid)
        return notes_data
    except Exception as e:
        logger.error(f"Error fetching notes for user {current_user.id}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not fetch notes: {str(e)}")

@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
async def create_user_note(
    note: NoteCreate,
    background_tasks: BackgroundTasks, # Inject BackgroundTasks
    current_user: User = Depends(get_current_user)
):
    """Create a new note and trigger background embedding."""
    try:
        # Convert string ID to UUID
        user_id_uuid = uuid.UUID(current_user.id)

        # Simple content validation
        if not note.content or not note.content.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Note content cannot be empty")

        # Create the note using RPC
        created_note_data = create_note(user_id=user_id_uuid, content=note.content)

        if created_note_data:
            logger.info(f"Note created successfully for user {current_user.id}. Triggering background embedding.")
            # --- Trigger background task ---
            # Pass the single created note as a list to the embedding function
            background_tasks.add_task(embed_and_store_notes, user_id_uuid, [created_note_data])
            # -------------------------------
            return created_note_data
        else:
            # This case indicates create_note returned None without raising an exception
            # which might mean a pre-RPC check failed or RPC returned no data/error
            logger.error(f"Failed to create note for user {current_user.id} (database function returned None without error)")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create note in database")

    except ValueError as ve:
        # Handle UUID conversion errors
        logger.error(f"Invalid UUID format: {str(ve)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid user ID format: {str(ve)}")

    except HTTPException:
        # Re-raise HTTP exceptions (like the 400 from validation)
        raise

    except Exception as e:
        # Handle any other unexpected errors, including potential RPC errors from create_note
        logger.error(f"Unexpected error creating note or triggering embedding: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Provide a more specific detail if possible, otherwise generic
        detail_msg = getattr(e, 'detail', "An unexpected server error occurred")
        status_code = getattr(e, 'status_code', status.HTTP_500_INTERNAL_SERVER_ERROR)
        raise HTTPException(status_code=status_code, detail=detail_msg) 