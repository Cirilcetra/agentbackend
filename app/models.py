from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChatRequest(BaseModel):
    """
    Request model for chat endpoint
    """
    message: str = Field(..., description="The message sent by the user")
    visitor_id: str = Field(..., description="Unique identifier for the visitor")
    visitor_name: Optional[str] = Field(None, description="Optional name for the visitor")
    target_user_id: Optional[str] = Field(None, description="Optional target user ID for user-specific chatbots")
    chatbot_id: Optional[str] = Field(None, description="Optional chatbot ID for sending message to a specific chatbot")


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
    target_user_id: Optional[str] = None
    timestamp: str


class ChatHistoryResponse(BaseModel):
    """
    Response model for chat history endpoint
    """
    history: List[ChatHistoryItem] = Field(default_factory=list)
    count: int


class Project(BaseModel):
    """
    Model for a project
    """
    id: Optional[str] = None
    user_id: Optional[str] = None
    title: str = Field(..., description="Project title")
    description: str = Field(..., description="Project description")
    category: str = Field(..., description="Project category (tech, design, other)")
    details: str = Field(..., description="Project details")
    content: Optional[str] = Field(None, description="Rich document content in Lexical format")
    content_html: Optional[str] = Field(None, description="HTML representation of the Lexical content for fallback display")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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
    projects: Optional[str] = None  # Keeping for backward compatibility
    project_list: Optional[List[Project]] = Field(default_factory=list, description="List of projects")
    interests: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_default: Optional[bool] = Field(False, description="Whether this is a default profile or a real one")


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


class Chatbot(BaseModel):
    """
    Model for a chatbot
    """
    id: Optional[str] = None
    user_id: str = Field(..., description="User ID that owns this chatbot")
    name: str = Field(..., description="Chatbot name")
    description: Optional[str] = Field(None, description="Chatbot description")
    is_public: bool = Field(False, description="Whether the chatbot is publicly accessible")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Chatbot configuration settings")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ChatbotListResponse(BaseModel):
    """
    Response model for listing chatbots
    """
    chatbots: List[Chatbot] = Field(default_factory=list)
    count: int = Field(0, description="Total number of chatbots") 