from typing import Dict, Any, List, Optional, Union, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
import uuid
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


from app.crud import chat_crud
from app.assistant import chat_agent
from app.assistant.schema import (
    Message,
    BookingDetails,
    AgentResponse,
    AgentState,
    UserContext,
)
from app.core.config import get_settings
from app.utils.logger_utils import get_logger
from app.utils.exception_utils import BadRequestException, ForbiddenException
from app.core.dependencies import get_sql_session


logger = get_logger(__name__)
settings = get_settings()


class ChatService:
    """
    Service for handling chat sessions and message processing with streaming support.
    """
    def _serialize_value(self, value: Any) -> Any:
        """
        Recursively serialize any value to JSON-compatible format.
        
        Args:
            value: The value to serialize
        
        Returns:
            JSON-compatible serialized value
        """
        if value is None:
            return None
        elif isinstance(value, datetime):
            return value.isoformat()
        elif hasattr(value, "model_dump"):
            return self._serialize_value(value.model_dump())
        elif hasattr(value, "dict"):
            return self._serialize_value(value.dict())
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            return [self._serialize_value(item) for item in value]
        elif isinstance(value, (str, int, float, bool)):
            return value
        else:
            return str(value)


    async def get_user_sessions(
        self, db: AsyncSession, user_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent chat sessions for a user.
        
        Args:
            db: Database session
            user_id: ID of the user
            limit: Maximum number of sessions to retrieve
        
        Returns:
            List of session dictionaries with session details
        """
        try:
            sessions = await chat_crud.get_user_sessions(db, user_id, limit=limit)

            result = []
            for session in sessions:
                title = session.title
                result.append(
                    {
                        "session_id": session.session_id,
                        "title": title,
                        "created_at": (
                            session.created_at.isoformat()
                            if session.created_at
                            else None
                        ),
                        "last_activity_at": (
                            session.updated_at.isoformat()
                            if session.updated_at
                            else None
                        ),
                        "is_active": session.is_active,
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Error getting recent sessions: {str(e)}")
            raise


    async def get_session_messages(
        self,
        db: AsyncSession,
        user_id: str,
        session_id: str,
        limit: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves all messages for a specific chat session.
        
        Args:
            db: Database session
            user_id: ID of the user
            session_id: ID of the chat session
            limit: Maximum number of messages to return
        
        Returns:
            Dictionary containing session messages and metadata or None
        """
        try:
            session = await chat_crud.get_session(db, session_id, user_id)
            if not session:
                raise ForbiddenException("Session not found or access denied.")

            thread_id = await chat_crud.get_session_thread(db, session_id, user_id)
            if not thread_id:
                return {
                    "session_id": session_id,
                    "thread_id": None,
                    "messages": [],
                    "total_messages": 0,
                    "returned_messages": 0,
                }

            config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}
            snapshot = await chat_agent.graph.aget_state(config)

            if snapshot is None:
                return {
                    "session_id": session_id,
                    "thread_id": thread_id,
                    "messages": [],
                    "total_messages": 0,
                    "returned_messages": 0,
                }

            state = snapshot.values
            messages = state.get("messages", [])

            seen_ids = set()
            unique_messages = []
            for msg in messages:
                msg_id = msg.id if hasattr(msg, "id") else msg.get("id")
                if msg_id and msg_id not in seen_ids:
                    seen_ids.add(msg_id)
                    unique_messages.append(msg)

            unique_messages.sort(
                key=lambda x: (
                    x.timestamp if hasattr(x, "timestamp") else x.get("timestamp", "")
                )
            )
            messages_to_return = unique_messages[-limit:] if limit else unique_messages

            serialized_messages = [
                self._serialize_value(
                    msg.model_dump() if hasattr(msg, "model_dump") else msg
                )
                for msg in messages_to_return
            ]

            return {
                "session_id": session_id,
                "thread_id": thread_id,
                "messages": serialized_messages,
                "total_messages": len(unique_messages),
                "returned_messages": len(serialized_messages),
            }

        except Exception as e:
            logger.error(f"Error getting session messages: {str(e)}")
            raise


    async def delete_session(
        self, db: AsyncSession, user_id: str, session_id: str
    ) -> bool:
        """
        Deletes all messages in a session and closes the session.
        
        Args:
            db: Database session
            user_id: ID of the user
            session_id: ID of the session to delete
        
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            session = await chat_crud.get_session(db, session_id, user_id)
            if not session:
                raise ForbiddenException("Session not found or access denied.")

            thread_id = await chat_crud.get_session_thread(db, session_id, user_id)
            if not thread_id:
                raise BadRequestException("No thread found to reset in this session.")

            if chat_agent.checkpointer:
                if hasattr(chat_agent.checkpointer, "adelete_thread"):
                    await chat_agent.checkpointer.adelete_thread(thread_id)
                elif hasattr(chat_agent.checkpointer, "delete_thread"):
                    chat_agent.checkpointer.delete_thread(thread_id)

            return await chat_crud.delete_session(db, session_id)

        except Exception as e:
            logger.error(f"Error resetting session {session_id}: {str(e)}")
            return False


    async def _summarize_messages(self, messages: List[Message]) -> str:
        """
        Summarize older messages to preserve context.
        
        Args:
            messages: List of messages to summarize
        
        Returns:
            Summarized text of the conversation
        """
        try:
            llm = ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_BASE_URL,
                temperature=0.3,
                streaming=False,
            )

            messages_text = "\n".join(
                [
                    f"{msg.role if hasattr(msg, 'role') else msg.get('role')}: {msg.content if hasattr(msg, 'content') else msg.get('content')}"
                    for msg in messages
                ]
            )

            summary_prompt = f"""Summarize the following conversation history concisely, preserving key information like:
- User preferences and requirements
- Cars or services discussed
- Important decisions or clarifications
- Booking details or dates mentioned

Conversation:
{messages_text}

Provide a brief, informative summary (2-3 paragraphs):"""

            response_messages = [
                SystemMessage(
                    content="You are a helpful assistant that summarizes conversations."
                ),
                HumanMessage(content=summary_prompt),
            ]

            response = await llm.ainvoke(response_messages)
            summary = response.content.strip()
            logger.info(f"Generated summary for {len(messages)} messages")
            return summary

        except Exception as e:
            logger.error(f"Failed to generate summary: {str(e)}")
            return "Previous conversation context available."


    async def _create_initial_state(
        self,
        user_id: str,
        query: str,
        session_id: str = None,
        booking_details: Optional[Union[Dict[str, Any], BookingDetails]] = None,
    ) -> AgentState:
        """
        Create initial agent state.
        
        Args:
            user_id: ID of the user
            query: User's query
            session_id: Optional session ID
            booking_details: Optional booking details
        
        Returns:
            Initial agent state dictionary
        """

        if not session_id:
            session_id = f"session_{uuid.uuid4()}"

        thread_id = session_id

        booking_details_obj = None
        if booking_details:
            if isinstance(booking_details, dict):
                booking_details_obj = BookingDetails(**booking_details)
            else:
                booking_details_obj = booking_details

        initial_message = Message(
            id=str(uuid.uuid4()),
            role="user",
            content=query,
            timestamp=datetime.now(timezone.utc),
        )

        return {
            "session_id": session_id,
            "thread_id": thread_id,
            "user_context": UserContext(
                user_id=user_id, session_id=session_id, thread_id=thread_id
            ),
            "messages": [initial_message],
            "current_query": query,
            "rephrased_query": None,
            "conversation_summary": None,
            "intent": None,
            "conversation_flow": None,
            "car_embeddings_used": [],
            "document_embeddings_used": [],
            "booking_results": None,
            "booking_details": booking_details_obj,
            "llm_response": None,
            "suggested_actions": [],
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "version": "1.0",
                "needs_clarification": False,
                "clarification_questions": [],
                "flow_analysis": {},
                "streaming": False,
                "chunk": False,
            },
        }


    async def process_query(
        self,
        user_id: str,
        query: str,
        session_id: str,
        booking_details: Optional[Union[Dict[str, Any], BookingDetails]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process query with streaming using astream_events.
        
        Args:
            user_id: ID of the user
            query: User's query
            session_id: ID of the session
            booking_details: Optional booking details
            config: Optional configuration dictionary
        
        Returns:
            Async generator yielding streaming events and final response
        """
        thread_id = session_id

        try:
            async for db in get_sql_session():
                session_obj, thread_id = await chat_crud.get_or_create_session(
                    db, user_id, session_id
                )
                session_id = session_obj.session_id
                break

        except Exception as e:
            logger.error(f"Failed to initialize session in DB: {str(e)}")
            yield {
                "type": "error",
                "error": "Failed to initialize chat session",
                "thread_id": thread_id,
                "complete": True,
            }
            return

        if config is None:
            config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}
        else:
            config["configurable"]["thread_id"] = thread_id

        try:
            snapshot = await chat_agent.graph.aget_state(config)

            if snapshot and snapshot.values:
                state = snapshot.values

                state["current_query"] = query
                state["rephrased_query"] = None
                state["intent"] = None
                state["car_embeddings_used"] = []
                state["document_embeddings_used"] = []
                state["booking_results"] = None
                state["llm_stream"] = None
                state["llm_response"] = None
                state["suggested_actions"] = []
                state["session_id"] = session_id

                if "conversation_summary" not in state:
                    state["conversation_summary"] = None

                preserved_flow = state.get("metadata", {}).get("conversation_flow")
                state["metadata"] = {
                    "created_at": state.get("metadata", {}).get(
                        "created_at", datetime.now(timezone.utc).isoformat()
                    ),
                    "version": "1.0",
                    "needs_clarification": False,
                    "clarification_questions": [],
                    "flow_analysis": {},
                    "streaming": False,
                    "chunk": False,
                }
                if preserved_flow:
                    state["metadata"]["conversation_flow"] = preserved_flow

                user_message = Message(
                    id=str(uuid.uuid4()),
                    role="user",
                    content=query,
                    timestamp=datetime.now(timezone.utc),
                )

                if "messages" not in state or state["messages"] is None:
                    state["messages"] = []

                existing_ids = {
                    msg.id if hasattr(msg, "id") else msg.get("id")
                    for msg in state["messages"]
                }
                if user_message.id not in existing_ids:
                    state["messages"].append(user_message)
            else:
                state = await self._create_initial_state(
                    user_id=user_id,
                    query=query,
                    session_id=session_id,
                    booking_details=booking_details,
                )

            messages_count = len(state.get("messages", []))
            if messages_count > 11:
                messages_to_summarize = state["messages"][:-11]
                state["messages"] = state["messages"][-11:]

                old_summary = state.get("conversation_summary", "")
                new_summary = await self._summarize_messages(messages_to_summarize)

                if old_summary:
                    state["conversation_summary"] = (
                        f"{old_summary}\n\nRecent context: {new_summary}"
                    )
                else:
                    state["conversation_summary"] = new_summary

            current_node = None
            final_state = None

            async for event in chat_agent.graph.astream_events(state, config):
                event_type = event.get("event")

                if event_type == "on_chain_start":
                    node_name = event.get("name")
                    if node_name and node_name not in ["LangGraph", "__start__"]:
                        current_node = node_name
                        yield {
                            "type": "node_start",
                            "node": node_name,
                            "complete": False,
                        }

                elif event_type == "on_chain_end":
                    node_name = event.get("name")
                    if node_name and node_name not in ["LangGraph", "__start__"]:
                        intent = (
                            event.get("data", {}).get("input", {}).get("intent", {})
                        )
                        yield {
                            "type": "node_complete",
                            "node": node_name,
                            "intent": intent.intent_type or None,
                            "sub_intent": intent.sub_intent or None,
                            "confidence": intent.confidence or None,
                            "status": "completed",
                            "complete": False,
                        }
                    elif node_name == "LangGraph":
                        final_state = event.get("data", {}).get("output", {})

                elif event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield {
                            "type": "token",
                            "node": current_node or "generate_response",
                            "token": chunk.content,
                            "complete": False,
                        }

            snapshot = await chat_agent.graph.aget_state(config)
            final_state = (
                snapshot.values
                if snapshot and snapshot.values
                else final_state or state
            )

            metadata = final_state.get("metadata", {}) or {}
            llm_response = final_state.get("llm_response") or ""

            response = AgentResponse(
                session_id=final_state.get("session_id") or session_id,
                thread_id=final_state.get("thread_id") or thread_id,
                query=query,
                rephrased_query=final_state.get("rephrased_query") or query,
                intent=final_state.get("intent"),
                conversation_flow=final_state.get("conversation_flow"),
                llm_response=llm_response,
                needs_clarification=metadata.get("needs_clarification", False),
                clarification_questions=metadata.get("clarification_questions", []),
                car_embeddings_used=final_state.get("car_embeddings_used", []),
                document_embeddings_used=final_state.get(
                    "document_embeddings_used", []
                ),
                booking_results=final_state.get("booking_results", []),
                suggested_actions=final_state.get("suggested_actions", []),
                flow_analysis=metadata.get("flow_analysis", {}),
                metadata=metadata,
            )

            yield {
                "type": "complete",
                "response": self._serialize_value(response.model_dump()),
                "complete": True,
            }

        except Exception as e:
            logger.error(f"Stream processing failed: {str(e)}")
            yield {
                "type": "error",
                "error": str(e),
                "thread_id": thread_id,
                "complete": True,
            }


chat_service = ChatService()
