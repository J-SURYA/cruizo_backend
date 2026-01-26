from langsmith import traceable


from app.assistant.schema import AgentState, DocumentsSubIntent, IntentType
from app.services.embedding_services import embedding_service
from app.services.retrieval_services import retrieval_service
from app.schemas.retrieval_schemas import SearchQuery, SearchIntent
from app.core.dependencies import get_sql_session
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


class DocumentsNode:
    """
    Node class for processing document queries (terms, FAQ, help, privacy).
    """
    @traceable(name="process_documents", run_type="chain")
    async def process_documents(self, state: AgentState) -> AgentState:
        """
        Process documents search based on the agent state and intent.

        Args:
            state (AgentState): The current state of the agent.

        Returns:
            AgentState: The updated state after processing documents.
        """
        try:
            if "metadata" not in state:
                state["metadata"] = {}

            intent = state["intent"]
            if intent.intent_type != IntentType.DOCUMENTS:
                logger.warning(
                    f"Invalid intent for documents node: {intent.intent_type}"
                )
                return state

            sub_intent = intent.sub_intent
            query = state.get("rephrased_query") or state["current_query"]
            query_embedding = await embedding_service.create_embedding(query)

            # Determine document types based on sub-intent
            doc_types = self._get_doc_types_for_sub_intent(sub_intent)

            from app.schemas.filter_schemas import SearchFilter

            filters = SearchFilter(doc_types=doc_types)

            search_query = SearchQuery(
                text_query=query,
                query_embedding=query_embedding,
                intent=SearchIntent(
                    intent_type="documents", confidence=intent.confidence
                ),
                filters=filters,
                top_k=10,
                similarity_threshold=0.3,
            )

            async for db in get_sql_session():

                search_results = await retrieval_service.search(db, search_query)

                if sub_intent == DocumentsSubIntent.TERMS:
                    state = await self._handle_terms(state, search_results)
                elif sub_intent == DocumentsSubIntent.FAQ:
                    state = await self._handle_faq(state, search_results)
                elif sub_intent == DocumentsSubIntent.PRIVACY:
                    state = await self._handle_privacy(state, search_results)
                elif sub_intent == DocumentsSubIntent.HELP:
                    state = await self._handle_help(state, search_results)
                else:
                    state = await self._handle_general_documents(state, search_results)

            return state

        except Exception as e:
            logger.error(f"Documents processing failed: {str(e)}", exc_info=True)
            state["llm_response"] = (
                "I encountered an error while searching documents. Please try again."
            )
            state["metadata"]["error"] = str(e)
            state["suggested_actions"] = [
                {"action": "retry", "label": "Try again"},
                {"action": "browse_help", "label": "Browse Help Center"},
                {"action": "contact_support", "label": "Contact Support"},
            ]
            return state


    def _get_doc_types_for_sub_intent(self, sub_intent: str) -> list:
        """
        Map sub-intent to document types.
        
        Args:
            sub_intent (str): The sub-intent of the document query.
        
        Returns:
            list: List of document types to search.
        """
        mapping = {
            DocumentsSubIntent.TERMS: ["terms"],
            DocumentsSubIntent.FAQ: ["faq"],
            DocumentsSubIntent.PRIVACY: ["privacy"],
            DocumentsSubIntent.HELP: ["help"],
        }
        return mapping.get(sub_intent, ["terms", "faq", "help", "privacy"])


    async def _handle_terms(self, state: AgentState, search_results) -> AgentState:
        """
        Handle terms and conditions queries.

        Args:
            state (AgentState): Current state of the agent.
            search_results: Results from the document search.

        Returns:
            AgentState: Updated state after handling terms queries.
        """
        if not search_results.results:
            state["metadata"]["results"] = False
            state["metadata"]["needs_clarification"] = True
            state["metadata"]["clarification_questions"] = [
                "What specific term or condition would you like to know about?",
                "Are you looking for rental terms, cancellation policy, or payment terms?",
            ]
            state["document_embeddings_used"] = []
        else:
            state["metadata"]["results"] = True
            state["metadata"]["source"] = "terms_documents"
            state["metadata"]["results_count"] = len(search_results.results)

            state["document_embeddings_used"] = [
                {
                    "doc_id": result.id,
                    "score": result.score,
                    "doc_type": result.doc_type,
                    "title": result.document_title,
                    "chunk_index": result.chunk_index,
                    "content_preview": result.content[:200] if result.content else "",
                    "metadata": result.metadata,
                }
                for result in search_results.results[:5]
            ]

            state["metadata"]["needs_clarification"] = False
            state["metadata"]["document_context"] = {
                "type": "terms",
                "total_sections": len(search_results.results),
                "primary_topics": self._extract_topics(search_results.results),
            }

        return state


    async def _handle_faq(self, state: AgentState, search_results) -> AgentState:
        """
        Handle FAQ queries.
        
        Args:
            state (AgentState): Current state of the agent.
            search_results: Results from the document search.

        Returns:
            AgentState: Updated state after handling FAQ queries.
        """
        if not search_results.results:
            state["metadata"]["results"] = False
            state["metadata"]["needs_clarification"] = True
            state["metadata"]["clarification_questions"] = [
                "What would you like help with?",
                "Are you looking for information about bookings, payments, or vehicle policies?",
            ]
            state["document_embeddings_used"] = []
        else:
            state["metadata"]["results"] = True
            state["metadata"]["source"] = "faq_documents"
            state["metadata"]["results_count"] = len(search_results.results)

            # Extract Q&A pairs
            qa_pairs = []
            for result in search_results.results[:5]:
                metadata = result.metadata or {}
                if metadata.get("is_qa"):
                    qa_pairs.append(
                        {
                            "question": metadata.get("question", ""),
                            "answer_preview": (
                                result.content[:300] if result.content else ""
                            ),
                            "category": metadata.get("category", "General"),
                            "score": result.score,
                        }
                    )

            state["document_embeddings_used"] = [
                {
                    "doc_id": result.id,
                    "score": result.score,
                    "doc_type": result.doc_type,
                    "title": result.document_title,
                    "chunk_index": result.chunk_index,
                    "content_preview": result.content[:200] if result.content else "",
                    "metadata": result.metadata,
                }
                for result in search_results.results[:5]
            ]

            state["metadata"]["needs_clarification"] = False
            state["metadata"]["document_context"] = {
                "type": "faq",
                "total_questions": len(qa_pairs),
                "qa_pairs": qa_pairs,
                "categories": list(set([qa["category"] for qa in qa_pairs])),
            }

        return state


    async def _handle_privacy(self, state: AgentState, search_results) -> AgentState:
        """
        Handle privacy policy queries.
        
        Args:
            state (AgentState): Current state of the agent.
            search_results: Results from the document search.

        Returns:
            AgentState: Updated state after handling privacy queries.
        """
        if not search_results.results:
            state["metadata"]["results"] = False
            state["metadata"]["needs_clarification"] = True
            state["metadata"]["clarification_questions"] = [
                "What aspect of our privacy policy are you interested in?",
                "Are you looking for information about data collection, usage, or your rights?",
            ]
            state["document_embeddings_used"] = []
        else:
            state["metadata"]["results"] = True
            state["metadata"]["source"] = "privacy_documents"
            state["metadata"]["results_count"] = len(search_results.results)

            state["document_embeddings_used"] = [
                {
                    "doc_id": result.id,
                    "score": result.score,
                    "doc_type": result.doc_type,
                    "title": result.document_title,
                    "chunk_index": result.chunk_index,
                    "content_preview": result.content[:200] if result.content else "",
                    "metadata": result.metadata,
                }
                for result in search_results.results[:5]
            ]

            state["metadata"]["needs_clarification"] = False
            state["metadata"]["document_context"] = {
                "type": "privacy",
                "total_sections": len(search_results.results),
                "primary_topics": self._extract_topics(search_results.results),
            }

        return state


    async def _handle_help(self, state: AgentState, search_results) -> AgentState:
        """
        Handle help center queries.

        Args:
            state (AgentState): Current state of the agent.
            search_results: Results from the document search.

        Returns:
            AgentState: Updated state after handling help queries.
        """
        if not search_results.results:
            state["metadata"]["results"] = False
            state["metadata"]["needs_clarification"] = True
            state["metadata"]["clarification_questions"] = [
                "What do you need help with?",
                "Are you looking for guides on how to book, make payments, or manage your account?",
            ]
            state["document_embeddings_used"] = []
        else:
            state["metadata"]["results"] = True
            state["metadata"]["source"] = "help_documents"
            state["metadata"]["results_count"] = len(search_results.results)

            state["document_embeddings_used"] = [
                {
                    "doc_id": result.id,
                    "score": result.score,
                    "doc_type": result.doc_type,
                    "title": result.document_title,
                    "chunk_index": result.chunk_index,
                    "content_preview": result.content[:200] if result.content else "",
                    "metadata": result.metadata,
                }
                for result in search_results.results[:5]
            ]

            state["metadata"]["needs_clarification"] = False
            state["metadata"]["document_context"] = {
                "type": "help",
                "total_guides": len(search_results.results),
                "primary_topics": self._extract_topics(search_results.results),
            }

        return state


    async def _handle_general_documents(
        self, state: AgentState, search_results
    ) -> AgentState:
        """
        Handle general document queries (multiple types).
        
        Args:
            state (AgentState): Current state of the agent.
            search_results: Results from the document search.

        Returns:
            AgentState: Updated state after handling general document queries.
        """
        if not search_results.results:
            state["metadata"]["results"] = False
            state["metadata"]["needs_clarification"] = True
            state["metadata"]["clarification_questions"] = [
                "What information are you looking for?",
                "Would you like to know about our terms, policies, or get help with something?",
            ]
            state["document_embeddings_used"] = []
        else:
            state["metadata"]["results"] = True
            state["metadata"]["source"] = "mixed_documents"
            state["metadata"]["results_count"] = len(search_results.results)

            # Group results by document type
            grouped_results = {}
            for result in search_results.results[:10]:
                doc_type = result.doc_type
                if doc_type not in grouped_results:
                    grouped_results[doc_type] = []
                grouped_results[doc_type].append(result)

            state["document_embeddings_used"] = [
                {
                    "doc_id": result.id,
                    "score": result.score,
                    "doc_type": result.doc_type,
                    "title": result.document_title,
                    "chunk_index": result.chunk_index,
                    "content_preview": result.content[:200] if result.content else "",
                    "metadata": result.metadata,
                }
                for result in search_results.results[:10]
            ]

            state["metadata"]["needs_clarification"] = False
            state["metadata"]["document_context"] = {
                "type": "general",
                "document_types": list(grouped_results.keys()),
                "results_by_type": {
                    doc_type: len(results)
                    for doc_type, results in grouped_results.items()
                },
                "primary_topics": self._extract_topics(search_results.results),
            }

        return state


    def _extract_topics(self, search_results) -> list:
        """
        Extract primary topics from search results.
        
        Args:
            search_results: Results from the document search.

        Returns:
            list: List of primary topics extracted.
        """
        topics = []
        for result in search_results[:5]:
            if result.document_title:
                topics.append(result.document_title)
            elif result.metadata and result.metadata.get("section_title"):
                topics.append(result.metadata["section_title"])

        return list(dict.fromkeys(topics))[:5]


documents_node = DocumentsNode()
