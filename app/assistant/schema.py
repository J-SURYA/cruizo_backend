from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, timezone
from enum import Enum


from app.schemas.filter_schemas import SearchFilter


class IntentType(str, Enum):
    """
    Schema for different user intent types.
    """
    INVENTORY = "inventory"
    DOCUMENTS = "documents"
    BOOKING = "booking"
    ABOUT = "about"
    GENERAL = "general"


class InventorySubIntent(str, Enum):
    """
    Schema for sub-intents related to inventory queries.
    """
    SEMANTIC_SEARCH = "semantic_search"
    CAR_DETAILS = "car_details"
    AVAILABILITY = "availability"
    RECOMMENDATION = "recommendation"


class DocumentsSubIntent(str, Enum):
    """
    Schema for sub-intents related to document queries.
    """
    TERMS = "terms"
    FAQ = "faq"
    PRIVACY = "privacy"
    HELP = "help"


class BookingSubIntent(str, Enum):
    """
    Schema for sub-intents related to booking queries.
    """
    BOOKING_HISTORY = "booking_history"
    PAYMENT_HISTORY = "payment_history"
    FREEZE_HISTORY = "freeze_history"


class AboutSubIntent(str, Enum):
    """
    Schema for sub-intents related to company information.
    """
    COMPANY = "company"
    SERVICES = "services"
    CONTACT = "contact"
    GENERAL_INFO = "general_info"


class GeneralSubIntent(str, Enum):
    """
    Schema for general conversational sub-intents.
    """
    GREETING = "greeting"
    CHITCHAT = "chitchat"
    UNCLEAR = "unclear"
    HELP_REQUEST = "help_request"


class Location(BaseModel):
    """
    Schema for geographical location.
    """
    longitude: float
    latitude: float


class Message(BaseModel):
    """
    Schema for chat messages.
    """
    id: str
    role: str
    content: str
    timestamp: datetime


class UserContext(BaseModel):
    """
    Schema for user context information.
    """
    user_id: str
    username: Optional[str] = None
    session_id: str
    thread_id: str
    role: str = "CUSTOMER"
    status: str = "ACTIVE"
    is_verified: bool = False
    tags: Optional[str] = None


class ConversationFlow(BaseModel):
    """
    Schema for managing conversation flow state.
    """
    flow_type: Optional[str] = None
    current_step: str = "start"
    context: Dict[str, Any] = {}
    pending_action: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_updated: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    history: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        model_config = ConfigDict(from_attributes=True)


class BookingDetails(BaseModel):
    """
    Schema for booking-related details.
    """
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    delivery_location: Optional[Location] = None
    pickup_location: Optional[Location] = None


class Intent(BaseModel):
    """
    Schema for user intent recognition.
    """
    intent_type: str
    sub_intent: Optional[str] = None
    confidence: float
    filters: SearchFilter
    extracted_start_date: Optional[datetime] = None
    extracted_end_date: Optional[datetime] = None
    has_dates: bool = False
    flow_continuation: bool = False
    continuation_context: Dict[str, Any] = {}


class AgentState(TypedDict):
    """
    Schema for the state of the agent during a conversation.
    """
    session_id: str
    thread_id: str
    user_context: UserContext

    messages: List[Message]
    current_query: str
    rephrased_query: Optional[str]
    conversation_summary: Optional[str]

    intent: Optional[Intent]
    conversation_flow: Optional[ConversationFlow]

    car_embeddings_used: List[Dict[str, Any]]
    document_embeddings_used: List[Dict[str, Any]]
    booking_results: Optional[List[Dict[str, Any]]]

    booking_details: Optional[BookingDetails]

    llm_stream: Optional[str]
    llm_response: Optional[str]

    suggested_actions: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class AgentResponse(BaseModel):
    """
    Schema for the agent's response after processing a user query.
    """
    session_id: str
    thread_id: str

    query: Optional[str] = None
    rephrased_query: Optional[str] = None

    intent: Optional[Intent] = None
    conversation_flow: Optional[ConversationFlow] = None

    llm_response: Optional[str] = None
    needs_clarification: bool = False
    clarification_questions: List[str] = []

    car_embeddings_used: List[Dict[str, Any]] = []
    document_embeddings_used: List[Dict[str, Any]] = []
    booking_results: Optional[List[Dict[str, Any]]] = None

    suggested_actions: List[Dict[str, Any]] = []
    flow_analysis: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}

    class Config:
        model_config = ConfigDict(from_attributes=True)
