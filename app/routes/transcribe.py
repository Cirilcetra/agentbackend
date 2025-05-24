import shutil
import tempfile
import openai
import os
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks
from app.auth import get_current_user, User  # Fixed import path

router = APIRouter()

# Configure OpenAI API key from environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
# else:
    # If the key is not set, the endpoint will raise an HTTPException

def delete_temp_file(path: str):
    """Helper function to delete a temporary file."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        # Log error during temp file deletion, if necessary
        print(f"Error deleting temporary file {path}: {e}")

@router.post("/transcribe-audio")
async def transcribe_audio_endpoint(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)  # Protects the endpoint
):
    if not openai.api_key:  # Check if API key was set from env var
        raise HTTPException(status_code=500, detail="OpenAI API key not configured. Please set the OPENAI_API_KEY environment variable.")

    if not audio_file.content_type or not audio_file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Invalid audio file type.")

    temp_file_path = None
    try:
        # Create a temporary file to store the uploaded audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_audio_file:  # Suffix can be adjusted
            shutil.copyfileobj(audio_file.file, tmp_audio_file)
            temp_file_path = tmp_audio_file.name
        
        # Add a background task to delete the temporary file after the request
        if temp_file_path: # Ensure temp_file_path was actually created
            background_tasks.add_task(delete_temp_file, temp_file_path)

        with open(temp_file_path, "rb") as af:
            # Using the new OpenAI v1.0.0 API syntax - removed await since it's synchronous
            transcription = openai.audio.transcriptions.create(
                model="whisper-1",
                file=af
            )
        
        return {"transcription": transcription.text if transcription else ""}

    except openai.APIError as e:
        # Handle OpenAI API errors
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(e)}")
    except Exception as e:
        # Handle other potential errors during file processing or transcription
        # Ensure temporary file is cleaned up if an error occurs before background task is effective (as per user's example)
        if temp_file_path and os.path.exists(temp_file_path) and not background_tasks.tasks:
             delete_temp_file(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Error transcribing audio: {str(e)}")
    finally:
        # Ensure the uploaded file stream is closed
        if hasattr(audio_file, 'file') and hasattr(audio_file.file, 'close'):
            if hasattr(audio_file.file, 'closed') and not audio_file.file.closed: # Check if not already closed
                audio_file.file.close()
            elif not hasattr(audio_file.file, 'closed'): # For file-like objects that might not have 'closed' attribute
                audio_file.file.close() 