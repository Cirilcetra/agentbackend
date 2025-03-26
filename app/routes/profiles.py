from fastapi import APIRouter, HTTPException, Depends, Header, Query
from typing import Optional, List
from datetime import datetime

from app import models
from app.database import get_profile_data, update_profile_data, add_project, update_project, delete_project
from app.embeddings import add_profile_to_vector_db
from app.routes.auth import get_current_user, User, get_optional_user

router = APIRouter()

@router.get("/", response_model=models.ProfileData)
async def get_profile(
    user_id: Optional[str] = Query(None, description="Specific user profile to retrieve"),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get the profile data for a specific user
    If user_id is provided, get that specific user's profile
    Otherwise, get the current authenticated user's profile
    """
    try:
        # Use current user's ID if no user_id provided and a user is authenticated
        target_user_id = user_id
        if not target_user_id and current_user:
            target_user_id = current_user.id
            
        if not target_user_id:
            raise HTTPException(
                status_code=401,
                detail="Authentication required to access profile data"
            )
            
        profile_data = get_profile_data(user_id=target_user_id)
        if not profile_data:
            # Return a default profile if none exists
            return models.ProfileData(
                bio="No bio available yet.",
                skills="No skills listed yet.",
                experience="No experience listed yet.",
                interests="No interests listed yet.",
                user_id=target_user_id
            )
        return models.ProfileData(**profile_data)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting profile data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get profile data: {str(e)}"
        )

@router.put("/", response_model=models.ProfileData)
async def update_profile(
    profile_data: models.ProfileData, 
    current_user: User = Depends(get_current_user),
):
    """
    Update the profile data for the authenticated user
    """
    try:
        # Convert to dict for database
        data_dict = profile_data.dict()
        
        # Override user_id with the authenticated user's ID
        data_dict["user_id"] = current_user.id
        
        # Add/update timestamp for updating
        data_dict["updated_at"] = datetime.utcnow().isoformat()
        
        # Update in database with the authenticated user's ID
        print(f"Updating profile for user {current_user.id} with data: {data_dict}")
        updated_data = update_profile_data(data_dict, user_id=current_user.id)
        if not updated_data:
            raise HTTPException(
                status_code=500,
                detail="Failed to update profile data in database"
            )
        
        # Add to vector database for search
        vector_update_success = add_profile_to_vector_db(updated_data, user_id=current_user.id)
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
    current_user: User = Depends(get_current_user),
):
    """
    Add a new project to the profile
    """
    try:
        # Convert to dict for database
        project_dict = project.dict()
        
        # Add project to database
        updated_profile = add_project(project_dict, user_id=current_user.id)
        if not updated_profile:
            raise HTTPException(
                status_code=500,
                detail="Failed to add project to profile"
            )
        
        # Update vector database
        vector_update_success = add_profile_to_vector_db(updated_profile, user_id=current_user.id)
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
    current_user: User = Depends(get_current_user),
):
    """
    Update an existing project
    """
    try:
        # Convert to dict for database
        project_dict = project.dict()
        
        # Update project in database
        updated_profile = update_project(project_id, project_dict, user_id=current_user.id)
        if not updated_profile:
            raise HTTPException(
                status_code=404,
                detail="Project not found"
            )
        
        # Update vector database
        vector_update_success = add_profile_to_vector_db(updated_profile, user_id=current_user.id)
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
    current_user: User = Depends(get_current_user),
):
    """
    Delete a project
    """
    try:
        # Delete project from database
        success = delete_project(project_id, user_id=current_user.id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Project not found"
            )
        
        # Get updated profile data
        profile_data = get_profile_data(user_id=current_user.id)
        
        # Update vector database
        vector_update_success = add_profile_to_vector_db(profile_data, user_id=current_user.id)
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