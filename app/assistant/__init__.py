from .agent import ChatAgent, chat_agent
from .schema import *
from .streaming import create_sse_stream


__version__ = "1.0.0"
__author__ = "Car Rental Assistant Team"


__all__ = [
    # Main agent
    "ChatAgent",
    "chat_agent",
    # Schemas
    "AgentState",
    "Intent",
    "SearchFilter",
    "ConversationFlow",
    "BookingDetails",
    "UserContext",
    "Location",
    "Message",
    # Enums
    "IntentType",
    "InventorySubIntent",
    "DocumentsSubIntent",
    "BookingSubIntent",
    "AboutSubIntent",
    "GeneralSubIntent",
    # Streaming
    "create_sse_stream",
    # Metadata
    "__version__",
    "__author__",
]
