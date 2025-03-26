# Profile Update System Improvements

## Summary of Changes

We've made significant improvements to the backend code, focusing on fixing issues with profile updates and enhancing the overall robustness of the system. The main problem was that profiles were not being properly updated in the database - specifically, skills and experiences were not being saved correctly.

## Backend Changes

### Key Issues Fixed

1. **User ID vs Profile ID**: 
   - Fixed the profile query and update operations to use `user_id` instead of `id` (profile ID)
   - Added fallback mechanisms when primary update method fails

2. **Authentication Headers**:
   - Added a mechanism to properly store and use authentication tokens
   - Ensured Supabase queries include proper authentication headers

3. **Error Handling**:
   - Added comprehensive error handling throughout the codebase
   - Included detailed logging to track operations and identify issues
   - Implemented fallback strategies for various error scenarios

4. **Data Structure**:
   - Fixed inconsistencies in data structure between frontend and backend
   - Added proper validation for required fields
   - Improved handling of optional fields

5. **Database Schema Fixes**:
   - Removed default values from the profiles table schema that were overriding user updates
   - Added NULL handling for empty fields to ensure proper updates
   - Updated database migrations for multi-user support
   - Added automatic timestamp updating for profile changes

### Specific File Changes

#### 1. `app/database.py`

- **Profile Retrieval**:
  - Enhanced `get_profile_data()` to explicitly filter by `user_id`
  - Added better logging for query execution
  - Ensured all required fields have default values

- **Profile Updates**:
  - Modified `update_profile_data()` to:
    - Use `user_id` for profile updates instead of profile `id`
    - Add a fallback mechanism to update by profile ID if user_id update fails
    - Include proper authentication headers
    - Remove `id` field from updates to prevent SQL conflicts
    - Return the latest profile data after updates

- **Project List Handling**:
  - Improved handling of the project_list field
  - Added error handling for project operations

#### 2. `app/routes/auth.py`

- Added a mechanism to store and retrieve the authentication token:
  ```python
  # Store the most recent user authentication token (for server-side use only)
  current_auth_token = None
  
  def get_auth_headers() -> Dict[str, str]:
      """
      Get the authorization headers for Supabase requests
      """
      headers = {}
      if current_auth_token:
          headers["Authorization"] = f"Bearer {current_auth_token}"
      return headers
  ```

- Enhanced the `get_current_user` function to store the token for use in Supabase requests

#### 3. `app/routes/profiles.py`

- Updated the profile update endpoint:
  - Removed `id` field to prevent SQL conflicts
  - Added better error logging
  - Improved response handling to always return the most recent profile data

#### 4. `app/main.py`

- Increased logging level to DEBUG for more detailed diagnostics
- Fixed issues in the deprecated profile update endpoints

#### 5. `migrations/schema/001_initial_schema.sql`

- Removed default values from profiles table columns that were causing update issues:
  ```sql
  CREATE TABLE profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    bio TEXT,  -- Removed default value
    skills TEXT,  -- Removed default value
    experience TEXT,  -- Removed default value
    interests TEXT,  -- Removed default value
    name TEXT,  -- Removed default value
    location TEXT,  -- Removed default value
    projects TEXT,  -- Removed default value
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id)
  );
  ```

- Kept default values in the profile creation trigger to ensure new users get defaults

#### 6. `migrations/schema/002_fix_profile_updates.sql`

- Added new migration file with fixes for the multi-user configuration:
  - Updated Row Level Security (RLS) policies for profiles
  - Added automatic timestamp updating for profile changes
  - Added database migration to reset default profile fields for existing users

## Frontend Changes Needed

To align with these backend changes, the following frontend updates are recommended:

### 1. Authentication Token Handling

```typescript
// In your auth service or context
const saveAuthToken = (token: string) => {
  localStorage.setItem('authToken', token);
  // Add to request headers for API calls
  api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
};
```

### 2. Profile Update Function

```typescript
const updateProfile = async (profileData: ProfileData) => {
  try {
    // Make sure the user_id is NOT included in the request body
    // The backend will use the authenticated user's ID
    const { id, user_id, ...dataToSend } = profileData;
    
    const response = await api.put('/profile', dataToSend);
    
    if (response.data.success) {
      // Use the fresh profile data returned from the backend
      setProfile(response.data.profile);
      return true;
    } else {
      console.error("Profile update failed:", response.data.message);
      return false;
    }
  } catch (error) {
    console.error("Error updating profile:", error);
    return false;
  }
};
```

### 3. API Client Configuration

```typescript
// api.ts or similar file
import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
});

// Add a request interceptor to include the auth token in all requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export default api;
```

### 4. Profile Form Component

```tsx
// In your ProfileForm component
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  setSubmitting(true);
  
  try {
    // Remove id and user_id from the form data
    // The backend will use these values from authentication
    const { id, user_id, ...profileToUpdate } = formData;
    
    const success = await updateProfile(profileToUpdate);
    
    if (success) {
      setMessage({ type: 'success', text: 'Profile updated successfully!' });
      // The backend now returns the latest profile data
      // No need to fetch it again
    } else {
      setMessage({ type: 'error', text: 'Failed to update profile. Please try again.' });
    }
  } catch (error) {
    setMessage({ type: 'error', text: 'An error occurred. Please try again.' });
    console.error(error);
  } finally {
    setSubmitting(false);
  }
};
```

### 5. Error Handling

```tsx
// In components that make API calls
const handleApiError = (error: any) => {
  if (error.response) {
    // The request was made and the server responded with a status code
    // that falls out of the range of 2xx
    console.error("Response error:", error.response.data);
    return error.response.data.message || "Server error. Please try again.";
  } else if (error.request) {
    // The request was made but no response was received
    console.error("Request error:", error.request);
    return "No response from server. Please check your connection.";
  } else {
    // Something happened in setting up the request that triggered an Error
    console.error("Error:", error.message);
    return "An error occurred. Please try again.";
  }
};
```

### 6. Project List Handling

```typescript
const addProject = async (projectData: ProjectData) => {
  try {
    // The backend will handle adding the user_id
    const response = await api.post('/profile/projects', projectData);
    
    if (response.data.success) {
      // Use the complete profile returned by the API
      setProfile(response.data.profile);
      return true;
    }
    return false;
  } catch (error) {
    console.error("Error adding project:", error);
    return false;
  }
};
```

## Testing the Changes

1. Start the backend server:
   ```bash
   cd backend
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. Use your frontend application to:
   - Log in (to get a proper authentication token)
   - Update profile information
   - Verify changes are saved correctly

3. Check the backend logs for detailed diagnostic information:
   - Look for proper profile querying by user_id
   - Confirm profile updates are using user_id
   - Validate that authentication tokens are being properly used

## Testing and Troubleshooting Tools

We've created a direct testing script (`test_profile_update.py`) that can be used to verify profile updates are working correctly with Supabase. This bypasses the API layer and tests the database connection directly.

You can use this script to:
1. Verify profile updates are being correctly applied
2. Debug any database connection issues
3. Test the multi-user configuration

## Potential Future Improvements

1. Implement refresh tokens for better authentication handling
2. Add more comprehensive validation on both frontend and backend
3. Enhance error reporting to provide more user-friendly messages
4. Implement more efficient data fetching with partial updates
5. Add automated testing for the critical profile update flow 