from langsmith import traceable


from app.assistant.schema import (
    AgentState,
    AboutSubIntent,
    GeneralSubIntent,
    IntentType,
)
from app.services.embedding_services import embedding_service
from app.services.retrieval_services import retrieval_service
from app.schemas.retrieval_schemas import SearchQuery, SearchIntent
from app.core.dependencies import get_sql_session
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


class ContextualNode:
    """
    Node class for processing about and general queries with contextual document search. 
    """
    @traceable(name="process_contextual", run_type="chain")
    async def process_contextual(self, state: AgentState) -> AgentState:
        """
        Process about or general query with appropriate document search strategy.
        
        Args:
            state (AgentState): Current state of the agent.

        Returns:
            AgentState: Updated state after contextual processing.
        """
        try:
            if "metadata" not in state:
                state["metadata"] = {}

            intent = state["intent"]
            if intent.intent_type not in [IntentType.ABOUT, IntentType.GENERAL]:
                logger.warning(
                    f"Invalid intent for contextual node: {intent.intent_type}"
                )
                return state

            if intent.intent_type == IntentType.ABOUT:
                return await self._process_about(state)
            elif intent.intent_type == IntentType.GENERAL:
                return await self._process_general(state)

            return state

        except Exception as e:
            logger.error(f"Contextual processing failed: {str(e)}", exc_info=True)
            state["llm_response"] = (
                "I encountered an error. Please try asking about our company or services."
            )
            state["metadata"]["error"] = str(e)
            state["suggested_actions"] = [
                {"action": "retry", "label": "Try again"},
                {"action": "browse_faq", "label": "Browse FAQ"},
                {"action": "contact_support", "label": "Contact Support"},
            ]
            return state


    async def _process_about(self, state: AgentState) -> AgentState:
        """
        Process about queries with document search.
        
        Args:
            state (AgentState): Current state of the agent.

        Returns:
            AgentState: Updated state after processing about queries.
        """
        sub_intent = state["intent"].sub_intent
        query = state.get("rephrased_query") or state["current_query"]

        query_embedding = await embedding_service.create_embedding(query)

        doc_types = ["faq", "help", "terms", "privacy"]

        from app.schemas.filter_schemas import SearchFilter

        filters = SearchFilter(doc_types=doc_types)

        search_query = SearchQuery(
            text_query=query,
            query_embedding=query_embedding,
            intent=SearchIntent(
                intent_type="documents", confidence=state["intent"].confidence
            ),
            filters=filters,
            top_k=3,
            similarity_threshold=0.4,
        )

        async for db in get_sql_session():
            search_results = await retrieval_service.search(db, search_query)

            if sub_intent == AboutSubIntent.COMPANY:
                state = await self._handle_company(state, search_results)
            elif sub_intent == AboutSubIntent.SERVICES:
                state = await self._handle_services(state, search_results)
            elif sub_intent == AboutSubIntent.CONTACT:
                state = await self._handle_contact(state, search_results)
            elif sub_intent == AboutSubIntent.GENERAL_INFO:
                state = await self._handle_general_info(state, search_results)
            else:
                state = await self._handle_general_about(state, search_results)

        return state


    async def _process_general(self, state: AgentState) -> AgentState:
        """
        Process general queries with minimal document search.
        
        Args:
            state (AgentState): Current state of the agent.

        Returns:
            AgentState: Updated state after processing general queries.
        """
        sub_intent = state["intent"].sub_intent
        query = state.get("rephrased_query") or state["current_query"]

        if sub_intent == GeneralSubIntent.GREETING:
            state = await self._handle_greeting(state)
        elif sub_intent == GeneralSubIntent.CHITCHAT:
            state = await self._handle_chitchat(state)
        elif sub_intent == GeneralSubIntent.HELP_REQUEST:
            state = await self._handle_help_request(state, query)
        elif sub_intent == GeneralSubIntent.UNCLEAR:
            state = await self._handle_unclear(state, query)
        else:
            state = await self._handle_general_default(state, query)

        return state


    async def _handle_company(self, state: AgentState, search_results) -> AgentState:
        """
        Handle company information queries.
        
        Args:
            state (AgentState): Current state of the agent.
            search_results: Results from the document search.

        Returns:
            AgentState: Updated state after handling company information queries.
        """
        state["metadata"]["source"] = "about_company"
        state["metadata"]["search_performed"] = True
        state["metadata"]["response_type"] = "about"

        if search_results.results:
            state["document_embeddings_used"] = [
                {
                    "doc_id": result.id,
                    "score": result.score,
                    "doc_type": result.doc_type,
                    "title": result.document_title,
                    "content": result.content,
                    "content_preview": result.content[:150] if result.content else "",
                    "metadata": result.metadata,
                }
                for result in search_results.results[:3]
            ]
            state["metadata"]["document_count"] = len(search_results.results)
        else:
            state["document_embeddings_used"] = []
            state["metadata"]["document_count"] = 0

        state["metadata"]["needs_clarification"] = False
        return state


    async def _handle_services(self, state: AgentState, search_results) -> AgentState:
        """
        Handle services information queries.
        
        Args:
            state (AgentState): Current state of the agent.
            search_results: Results from the document search.

        Returns:
            AgentState: Updated state after handling services information queries.
        """
        state["metadata"]["source"] = "about_services"
        state["metadata"]["search_performed"] = True
        state["metadata"]["response_type"] = "about"

        if search_results.results:
            state["document_embeddings_used"] = [
                {
                    "doc_id": result.id,
                    "score": result.score,
                    "doc_type": result.doc_type,
                    "title": result.document_title,
                    "content": result.content,
                    "content_preview": result.content[:150] if result.content else "",
                    "metadata": result.metadata,
                }
                for result in search_results.results[:3]
            ]
            state["metadata"]["document_count"] = len(search_results.results)
        else:
            state["document_embeddings_used"] = []
            state["metadata"]["document_count"] = 0

        state["metadata"]["needs_clarification"] = False
        return state


    async def _handle_contact(self, state: AgentState, search_results) -> AgentState:
        """
        Handle contact information queries.
        
        Args:
            state (AgentState): Current state of the agent.
            search_results: Results from the document search.

        Returns:
            AgentState: Updated state after handling contact information queries.
        """
        state["metadata"]["source"] = "about_contact"
        state["metadata"]["search_performed"] = True
        state["metadata"]["response_type"] = "about"

        if search_results.results:
            state["document_embeddings_used"] = [
                {
                    "doc_id": result.id,
                    "score": result.score,
                    "doc_type": result.doc_type,
                    "title": result.document_title,
                    "content": result.content,
                    "content_preview": result.content[:150] if result.content else "",
                    "metadata": result.metadata,
                }
                for result in search_results.results[:3]
            ]
            state["metadata"]["document_count"] = len(search_results.results)
        else:
            state["document_embeddings_used"] = []
            state["metadata"]["document_count"] = 0

        state["metadata"]["needs_clarification"] = False
        return state


    async def _handle_general_info(
        self, state: AgentState, search_results
    ) -> AgentState:
        """
        Handle general information queries.
        
        Args:
            state (AgentState): Current state of the agent.
            search_results: Results from the document search.

        Returns:
            AgentState: Updated state after handling general information queries.
        """
        state["metadata"]["source"] = "about_general"
        state["metadata"]["search_performed"] = True
        state["metadata"]["response_type"] = "about"

        if search_results.results:
            state["document_embeddings_used"] = [
                {
                    "doc_id": result.id,
                    "score": result.score,
                    "doc_type": result.doc_type,
                    "title": result.document_title,
                    "content": result.content,
                    "content_preview": result.content[:150] if result.content else "",
                    "metadata": result.metadata,
                }
                for result in search_results.results[:3]
            ]
            state["metadata"]["document_count"] = len(search_results.results)
        else:
            state["document_embeddings_used"] = []
            state["metadata"]["document_count"] = 0

        state["metadata"]["needs_clarification"] = False
        return state


    async def _handle_general_about(
        self, state: AgentState, search_results
    ) -> AgentState:
        """
        Handle general about queries.
        
        Args:
            state (AgentState): Current state of the agent.
            search_results: Results from the document search.

        Returns:
            AgentState: Updated state after handling general about queries.
        """
        state["metadata"]["source"] = "about_mixed"
        state["metadata"]["search_performed"] = True
        state["metadata"]["response_type"] = "about"

        if search_results.results:
            state["document_embeddings_used"] = [
                {
                    "doc_id": result.id,
                    "score": result.score,
                    "doc_type": result.doc_type,
                    "title": result.document_title,
                    "content": result.content,
                    "content_preview": result.content[:150] if result.content else "",
                    "metadata": result.metadata,
                }
                for result in search_results.results[:3]
            ]
            state["metadata"]["document_count"] = len(search_results.results)
        else:
            state["document_embeddings_used"] = []
            state["metadata"]["document_count"] = 0

        state["metadata"]["needs_clarification"] = False
        return state


    async def _handle_greeting(self, state: AgentState) -> AgentState:
        """
        Handle greeting queries.
        
        Args:
            state (AgentState): Current state of the agent.

        Returns:
            AgentState: Updated state after handling greeting queries.
        """
        state["metadata"]["source"] = "greeting"
        state["metadata"]["search_performed"] = False
        state["metadata"]["response_type"] = "general"
        state["metadata"]["needs_clarification"] = False
        state["document_embeddings_used"] = []
        return state


    async def _handle_chitchat(self, state: AgentState) -> AgentState:
        """
        Handle chitchat queries.
        
        Args:
            state (AgentState): Current state of the agent.

        Returns:
            AgentState: Updated state after handling chitchat queries.
        """
        state["metadata"]["source"] = "chitchat"
        state["metadata"]["search_performed"] = False
        state["metadata"]["response_type"] = "general"
        state["metadata"]["needs_clarification"] = False
        state["document_embeddings_used"] = []
        return state


    async def _handle_help_request(self, state: AgentState, query: str) -> AgentState:
        """
        Handle help request with document search.
        
        Args:
            state (AgentState): Current state of the agent.
            query (str): The user's query.

        Returns:
            AgentState: Updated state after handling help request.
        """
        query_embedding = await embedding_service.create_embedding(query)

        doc_types = ["faq", "help"]

        from app.schemas.filter_schemas import SearchFilter

        filters = SearchFilter(doc_types=doc_types)

        search_query = SearchQuery(
            text_query=query,
            query_embedding=query_embedding,
            intent=SearchIntent(
                intent_type="documents", confidence=state["intent"].confidence
            ),
            filters=filters,
            top_k=3,
            similarity_threshold=0.4,
        )

        async for db in get_sql_session():
            search_results = await retrieval_service.search(db, search_query)

            if search_results.results:
                state["document_embeddings_used"] = [
                    {
                        "doc_id": result.id,
                        "score": result.score,
                        "doc_type": result.doc_type,
                        "title": result.document_title,
                        "content": result.content,
                        "content_preview": (
                            result.content[:150] if result.content else ""
                        ),
                        "metadata": result.metadata,
                    }
                    for result in search_results.results[:3]
                ]
                state["metadata"]["document_count"] = len(search_results.results)
            else:
                state["document_embeddings_used"] = []
                state["metadata"]["document_count"] = 0

        state["metadata"]["source"] = "help_request"
        state["metadata"]["search_performed"] = True
        state["metadata"]["response_type"] = "general"
        state["metadata"]["needs_clarification"] = False
        return state


    async def _handle_unclear(self, state: AgentState, query: str) -> AgentState:
        """
        Handle unclear queries with minimal search.
        
        Args:
            state (AgentState): Current state of the agent.
            query (str): The user's query.

        Returns:
            AgentState: Updated state after handling unclear queries.
        """
        query_embedding = await embedding_service.create_embedding(query)

        doc_types = ["faq"]

        from app.schemas.filter_schemas import SearchFilter

        filters = SearchFilter(doc_types=doc_types)

        search_query = SearchQuery(
            text_query=query,
            query_embedding=query_embedding,
            intent=SearchIntent(
                intent_type="documents", confidence=state["intent"].confidence
            ),
            filters=filters,
            top_k=2,
            similarity_threshold=0.5,
        )

        async for db in get_sql_session():
            search_results = await retrieval_service.search(db, search_query)

            if search_results.results:
                state["document_embeddings_used"] = [
                    {
                        "doc_id": result.id,
                        "score": result.score,
                        "doc_type": result.doc_type,
                        "title": result.document_title,
                        "content": result.content,
                        "content_preview": (
                            result.content[:150] if result.content else ""
                        ),
                        "metadata": result.metadata,
                    }
                    for result in search_results.results[:2]
                ]
                state["metadata"]["document_count"] = len(search_results.results)
            else:
                state["document_embeddings_used"] = []
                state["metadata"]["document_count"] = 0

        state["metadata"]["source"] = "unclear"
        state["metadata"]["search_performed"] = True
        state["metadata"]["response_type"] = "general"
        state["metadata"]["needs_clarification"] = True
        return state


    async def _handle_general_default(
        self, state: AgentState, query: str
    ) -> AgentState:
        """
        Handle general default queries.
        
        Args:
            state (AgentState): Current state of the agent.
            query (str): The user's query.

        Returns:
            AgentState: Updated state after handling general default queries.
        """
        state["metadata"]["source"] = "general_default"
        state["metadata"]["search_performed"] = False
        state["metadata"]["response_type"] = "general"
        state["metadata"]["needs_clarification"] = False
        state["document_embeddings_used"] = []
        return state


contextual_node = ContextualNode()
