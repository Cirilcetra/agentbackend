from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class ChatRequest(BaseModel):
    """
    Request model for chat endpoint
    """
    message: str = Field(..., description="The message sent by the user")
    visitor_id: str = Field(..., description="Unique identifier for the visitor")
    visitor_name: Optional[str] = Field(None, description="Optional name for the visitor")
    chatbot_id: str = Field(..., description="Identifier for the specific chatbot to chat with")


class ChatResponse(BaseModel):
    """
    Response model for chat endpoint
    """
    response: str = Field(..., description="The response from the AI assistant")
    query_time_ms: float = Field(..., description="Time taken to process the query in milliseconds")


class ChatHistoryItem(BaseModel):
    """
    Model for a single chat history item
    """
    id: str
    message: str
    sender: str
    response: Optional[str] = None
    visitor_id: str
    visitor_name: Optional[str] = None
    timestamp: str
    conversation_id: Optional[str] = None


class ChatHistoryResponse(BaseModel):
    """
    Response model for chat history endpoint
    """
    success: bool = Field(True, description="Whether the request was successful")
    history: List[ChatHistoryItem] = Field(default_factory=list)
    count: Optional[int] = Field(None, description="Total number of messages")


class Settings(BaseModel):
    # Settings fields...
    pass


class ProfileData(BaseModel):
    """
    Model for profile data
    """
    id: Optional[str] = None
    user_id: Optional[str] = None
    name: Optional[str] = Field(None, description="User's name")
    location: Optional[str] = Field(None, description="User's location")
    bio: str
    skills: str
    experience: str
    interests: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    calendly_link: Optional[str] = Field(None, description="Calendly link")
    meeting_rules: Optional[str] = Field(None, description="Rules for meeting scheduling")
    profile_photo_url: Optional[str] = Field(None, description="URL to user's profile photo")


class ChatbotModel(BaseModel):
    """
    Model for a chatbot
    """
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    public_url_slug: Optional[str] = None
    description: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    is_public: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True


class ChatbotUpdateRequest(BaseModel):
    """
    Request model for updating chatbot configuration.
    Only includes fields that should be updatable via this endpoint.
    """
    configuration: Optional[Dict[str, Any]] = Field(None, description="Configuration options for the chatbot")
    public_url_slug: Optional[str] = Field(None, description="Custom URL slug for public access")
    # Add other fields like name, description if they should be updatable here
    # name: Optional[str] = None
    # description: Optional[str] = None


class VisitorModel(BaseModel):
    """
    Model for a visitor
    """
    id: Optional[str] = None
    visitor_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None


class AdminLoginRequest(BaseModel):
    """
    Request model for admin login
    """
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    """
    Response model for admin login
    """
    success: bool
    token: Optional[str] = None
    message: Optional[str] = None


class AdminCreateRequest(BaseModel):
    """
    Request model for creating an admin user
    """
    email: str = Field(..., description="Admin user email")
    password: str = Field(..., description="Admin user password")
    signup_code: str = Field(..., description="Signup code for authorization")


class AdminCreateResponse(BaseModel):
    """
    Response model for admin user creation
    """
    success: bool
    message: Optional[str] = None
    user_id: Optional[str] = None


class AdminInfoResponse(BaseModel):
    """
    Response model for admin user info
    """
    id: str
    email: str
    success: bool


class ErrorResponse(BaseModel):
    """
    Standard error response
    """
    error: str
    detail: Optional[str] = None


# Note Models
class NoteBase(BaseModel):
    content: str


class NoteCreate(NoteBase):
    pass  # Inherits content from NoteBase


class NoteRead(NoteBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True  # For SQLAlchemy or similar ORMs
        from_attributes = True  # Pydantic v2 equivalent of orm_mode 


class ChatMessage(BaseModel):
    role: str
    content: str
    # ... rest of file ... 