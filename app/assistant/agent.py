import os
from langgraph.graph import StateGraph, END

from app.assistant.schema import AgentState
from app.assistant.nodes import (
    classify_intent_node, 
    inventory_node, 
    documents_node,
    contextual_node, 
    booking_node, 
    generate_response_node,
)
from app.core.config import get_settings
from app.utils.logger_utils import get_logger
from app.core.dependencies import get_postgres_checkpointer


logger = get_logger(__name__)
settings = get_settings()


class ChatAgent:
    """
    Class representing the chat agent using LangGraph workflow.
    """
    def __init__(self):
        if settings.LANGSMITH_API_KEY:
            self._setup_langsmith()

        self.workflow = self._build_workflow()
        self.graph = self.workflow.compile()
        self.checkpointer = None
        self._initialized = False


    async def initialize(self):
        """
        Initialize the agent with checkpointer.
        """
        if not self._initialized:
            self.checkpointer = await get_postgres_checkpointer()
            self.graph = self.workflow.compile(checkpointer=self.checkpointer)
            self._initialized = True
            logger.info("Chat agent initialized with checkpointer")


    def _setup_langsmith(self):
        """
        Setup LangSmith tracing.
        """
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
        logger.info("LangSmith tracing enabled")


    def _build_workflow(self) -> StateGraph:
        """
        Build LangGraph workflow with all nodes.

        Args:
            None

        Returns:
            StateGraph: The constructed workflow graph.
        """
        workflow = StateGraph(AgentState)

        workflow.add_node("classify_intent", classify_intent_node.classify_intent)
        workflow.add_node("process_inventory", inventory_node.process_inventory)
        workflow.add_node("process_documents", documents_node.process_documents)
        workflow.add_node("process_contextual", contextual_node.process_contextual)
        workflow.add_node("process_booking", booking_node.process_booking)
        workflow.add_node("generate_response", generate_response_node.generate_response)

        workflow.set_entry_point("classify_intent")

        workflow.add_conditional_edges(
            "classify_intent",
            self._route_after_classification,
            {
                "inventory": "process_inventory",
                "documents": "process_documents",
                "contextual": "process_contextual",
                "booking": "process_booking",
                "end": END,
            },
        )

        workflow.add_edge("process_inventory", "generate_response")
        workflow.add_edge("process_documents", "generate_response")
        workflow.add_edge("process_contextual", "generate_response")
        workflow.add_edge("process_booking", "generate_response")
        workflow.add_edge("generate_response", END)

        return workflow


    def _route_after_classification(self, state: AgentState) -> str:
        """
        Route to appropriate node based on intent.
        
        Args:
            state (AgentState): The current state of the agent.

        Returns:
            str: The next node to route to.
        """
        intent = state.get("intent")

        if not intent:
            return "end"

        if intent.intent_type == "inventory":
            return "inventory"

        if intent.intent_type == "documents":
            return "documents"

        if intent.intent_type == "booking":
            return "booking"

        if intent.intent_type in ["about", "general"]:
            return "contextual"

        return "end"


chat_agent = ChatAgent()
graph = chat_agent.graph
