from fastapi import APIRouter, HTTPException, Depends, Header, Query
from typing import Optional, List
from datetime import datetime

from app import models
from app.database import get_profile_data, update_profile_data, add_project, update_project, delete_project
from app.embeddings import add_profile_to_vector_db
from app.routes.admin import verify_admin_token

router = APIRouter()

@router.get("/", response_model=models.ProfileData)
async def get_profile(user_id: Optional[str] = Query(None, description="Specific user profile to retrieve")):
    """
    Get the profile data
    If user_id is provided, get that specific user's profile
    Otherwise, return the default profile
    """
    try:
        profile_data = get_profile_data(user_id=user_id)
        if not profile_data:
            # Return a default profile if none exists
            return models.ProfileData(
                bio="No bio available yet.",
                skills="No skills listed yet.",
                experience="No experience listed yet.",
                projects="No projects listed yet.",
                interests="No interests listed yet."
            )
        return models.ProfileData(**profile_data)
    
    except Exception as e:
        print(f"Error getting profile data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get profile data: {str(e)}"
        )

@router.put("/", response_model=models.ProfileData)
async def update_profile(
    profile_data: models.ProfileData, 
    user = Depends(verify_admin_token),
):
    """
    Update the profile data for the authenticated user
    """
    try:
        # Convert to dict for database
        data_dict = profile_data.dict()
        
        # Add/update timestamp for updating
        data_dict["updated_at"] = datetime.utcnow().isoformat()
        
        # Update in database with the authenticated user's ID
        print(f"Updating profile for user {user.id} with data: {data_dict}")
        updated_data = update_profile_data(data_dict, user_id=user.id)
        if not updated_data:
            raise HTTPException(
                status_code=500,
                detail="Failed to update profile data in database"
            )
        
        # Add to vector database for search
        vector_update_success = add_profile_to_vector_db(data_dict, user_id=user.id)
        if not vector_update_success:
            print("Warning: Failed to update vector database")
        
        return models.ProfileData(**updated_data)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating profile data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update profile data: {str(e)}"
        )

@router.post("/projects", response_model=models.ProfileData)
async def create_project(
    project: models.Project,
    user = Depends(verify_admin_token),
):
    """
    Add a new project to the profile
    """
    try:
        # Convert to dict for database
        project_dict = project.dict()
        
        # Add project to database
        updated_profile = add_project(project_dict, user_id=user.id)
        if not updated_profile:
            raise HTTPException(
                status_code=500,
                detail="Failed to add project to profile"
            )
        
        # Update vector database
        vector_update_success = add_profile_to_vector_db(updated_profile, user_id=user.id)
        if not vector_update_success:
            print("Warning: Failed to update vector database with new project")
        
        return models.ProfileData(**updated_profile)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error adding project: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add project: {str(e)}"
        )

@router.put("/projects/{project_id}", response_model=models.ProfileData)
async def edit_project(
    project_id: str,
    project: models.Project,
    user = Depends(verify_admin_token),
):
    """
    Update an existing project
    """
    try:
        # Convert to dict for database
        project_dict = project.dict()
        
        # Update project in database
        updated_profile = update_project(project_id, project_dict, user_id=user.id)
        if not updated_profile:
            raise HTTPException(
                status_code=404,
                detail="Project not found"
            )
        
        # Update vector database
        vector_update_success = add_profile_to_vector_db(updated_profile, user_id=user.id)
        if not vector_update_success:
            print("Warning: Failed to update vector database with updated project")
        
        return models.ProfileData(**updated_profile)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating project: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update project: {str(e)}"
        )

@router.delete("/projects/{project_id}", response_model=dict)
async def remove_project(
    project_id: str,
    user = Depends(verify_admin_token),
):
    """
    Delete a project
    """
    try:
        # Delete project from database
        success = delete_project(project_id, user_id=user.id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Project not found"
            )
        
        # Get updated profile data
        profile_data = get_profile_data(user_id=user.id)
        
        # Update vector database
        vector_update_success = add_profile_to_vector_db(profile_data, user_id=user.id)
        if not vector_update_success:
            print("Warning: Failed to update vector database after project deletion")
        
        return {"success": True, "message": "Project deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting project: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete project: {str(e)}"
        ) 