import json
import re
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import traceable


from app.assistant.schema import AgentState, Intent, SearchFilter, ConversationFlow
from app.core.config import get_settings
from app.utils.logger_utils import get_logger
from app.assistant.prompts import get_classify_intent_prompt


logger = get_logger(__name__)
settings = get_settings()


class ClassifyIntentNode:
    """
    Node class to classify user intent using an LLM and update the agent state accordingly.
    """
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_BASE_URL,
            streaming=False,
            temperature=0.1,
        )


    @traceable(name="classify_intent", run_type="chain")
    async def classify_intent(self, state: AgentState) -> AgentState:
        """
        Classify user intent and return updated state.
        
        Args:
            state (AgentState): Current state of the agent.

        Returns:
            AgentState: Updated state with classified intent and related info.
        """
        try:
            flow_context = self._format_flow_context(state.get("conversation_flow"))
            system_prompt = get_classify_intent_prompt(flow_context)

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=state["current_query"]),
            ]

            response = await self.llm.ainvoke(messages)
            full_response = response.content
            result = self._parse_llm_response(full_response, state)

            if isinstance(result.get("intent"), dict):
                try:
                    result["intent"] = Intent(**result["intent"])
                except Exception as e:
                    logger.error(f"Failed to convert intent dict in result: {e}")
                    result["intent"] = Intent(
                        intent_type="general",
                        sub_intent=None,
                        confidence=0.1,
                        filters=SearchFilter(),
                        flow_continuation=False,
                        continuation_context={},
                    )

            flow_update = self._update_conversation_flow(state, result["intent"])

            state["intent"] = result.get("intent")
            state["rephrased_query"] = result.get("rephrased_query")
            if "conversation_flow" in flow_update:
                state["conversation_flow"] = flow_update["conversation_flow"]
            state["llm_response"] = "Intent classification completed"

            if "metadata" not in state:
                state["metadata"] = {}

            if result.get("needs_clarification"):
                state["metadata"]["needs_clarification"] = True
                state["metadata"]["clarification_questions"] = result.get(
                    "clarification_questions", []
                )

            if result.get("flow_analysis"):
                state["metadata"]["flow_analysis"] = result.get("flow_analysis")

            return state

        except Exception as e:
            logger.error(f"Intent classification failed: {str(e)}")
            error_response = self._create_error_response(state, e)

            state["intent"] = error_response["intent"]
            state["rephrased_query"] = error_response["rephrased_query"]
            state["llm_response"] = f"Error: {str(e)}"

            if "metadata" not in state:
                state["metadata"] = {}

            state["metadata"]["needs_clarification"] = error_response.get(
                "needs_clarification", True
            )
            state["metadata"]["clarification_questions"] = error_response.get(
                "clarification_questions", []
            )
            state["metadata"]["flow_analysis"] = error_response.get(
                "flow_analysis", {"error": str(e)}
            )

            return state


    def _format_flow_context(self, flow: ConversationFlow = None) -> str:
        """
        Format flow context for prompt.
        
        Args:
            flow (ConversationFlow, optional): Current conversation flow.

        Returns:
            str: Formatted flow context string.
        """
        if not flow:
            return "No active conversation flow."

        return f"""
        Active Flow: {flow.flow_type}
        Current Step: {flow.current_step}
        Pending Action: {flow.pending_action or 'None'}
        Flow Context: {json.dumps(flow.context, default=str, indent=2)}
        """


    def _parse_llm_response(
        self, llm_response: str, state: AgentState
    ) -> Dict[str, Any]:
        """
        Parse and validate LLM response.
        
        Args:
            llm_response (str): Raw response from the LLM.
            state (AgentState): Current state of the agent.
        
        Returns:
            Dict[str, Any]: Parsed intent and related information.
        """
        try:
            if "```json" in llm_response:
                json_str = llm_response.split("```json")[1].split("```")[0].strip()
            elif "```" in llm_response:
                json_str = llm_response.split("```")[1].split("```")[0].strip()
            else:
                json_str = llm_response.strip()

            json_str = self._repair_json(json_str)

            data = json.loads(json_str)

            if "intent" not in data:
                raise ValueError("Missing 'intent' in LLM response")

            filters_data = data["intent"].get("filters", {})
            search_filter = SearchFilter(**filters_data)

            start_date = self._parse_date(data["intent"].get("extracted_start_date"))
            end_date = self._parse_date(data["intent"].get("extracted_end_date"))

            intent = Intent(
                intent_type=data["intent"]["intent_type"],
                sub_intent=data["intent"].get("sub_intent"),
                confidence=float(data["intent"]["confidence"]),
                filters=search_filter,
                extracted_start_date=start_date,
                extracted_end_date=end_date,
                has_dates=data["intent"].get("has_dates", False),
                flow_continuation=data["intent"].get("flow_continuation", False),
                continuation_context=data["intent"].get("continuation_context", {}),
            )

            logger.info(
                f"Intent classified: {intent.intent_type} sub_intent: {intent.sub_intent} (confidence: {intent.confidence})"
            )
            return {
                "rephrased_query": data["rephrased_query"],
                "intent": intent,
                "needs_clarification": data.get("needs_clarification", False),
                "clarification_questions": data.get("clarification_questions", []),
                "flow_analysis": data.get("flow_analysis", {}),
            }

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return self._create_fallback_intent_response(state)


    def _repair_json(self, json_str: str) -> str:
        """
        Attempt to repair common JSON formatting issues.
        
        Args:
            json_str (str): JSON string to repair.

        Returns:
            str: Repaired JSON string.
        """
        try:
            json_str = re.sub(r",\s*}", "}", json_str)
            json_str = re.sub(r",\s*]", "]", json_str)

            open_braces = json_str.count("{")
            close_braces = json_str.count("}")
            open_brackets = json_str.count("[")
            close_brackets = json_str.count("]")

            if open_braces > close_braces:
                json_str += "}" * (open_braces - close_braces)
            if open_brackets > close_brackets:
                json_str += "]" * (open_brackets - close_brackets)

            json.loads(json_str)
            return json_str

        except json.JSONDecodeError:
            return json_str


    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse date string.
        
        Args:
            date_str (Optional[str]): Date string to parse.

        Returns:
            Optional[datetime]: Parsed datetime object or None.
        """
        if not date_str:
            return None

        try:
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except ValueError:
                    continue
            return None
        except Exception:
            return None


    def _create_fallback_intent_response(self, state: AgentState) -> Dict[str, Any]:
        """
        Create a safe fallback response when parsing fails.
        
        Args:
            state (AgentState): Current state of the agent.

        Returns:
            Dict[str, Any]: Fallback intent response.
        """
        fallback_intent = Intent(
            intent_type="general",
            sub_intent=None,
            confidence=0.3,
            filters=SearchFilter(),
            flow_continuation=False,
            continuation_context={},
        )

        return {
            "rephrased_query": state["current_query"],
            "intent": fallback_intent,
            "needs_clarification": False,
            "clarification_questions": [],
            "flow_analysis": {"parsing_failed": True},
        }


    def _update_conversation_flow(
        self, state: AgentState, intent: Intent
    ) -> Dict[str, Any]:
        """
        Update conversation flow based on intent.
        
        Args:
            state (AgentState): Current state of the agent.

        Returns:
            Dict[str, Any]: Updated conversation flow info.
        """
        if isinstance(intent, dict):
            try:
                intent = Intent(**intent)
            except Exception as e:
                logger.error(f"Failed to convert intent dict to Intent object: {e}")
                intent = Intent(
                    intent_type="general",
                    sub_intent=None,
                    confidence=0.1,
                    filters=SearchFilter(),
                    flow_continuation=False,
                    continuation_context={},
                )

        flow = state.get("conversation_flow")

        if not flow:
            if intent.intent_type == "booking" and intent.has_dates:
                new_flow = ConversationFlow(
                    flow_type="booking",
                    current_step="dates_provided",
                    context={"dates_provided": True},
                    pending_action="location",
                )
                return {"conversation_flow": new_flow}
            return {}

        if intent.flow_continuation:
            flow.current_step = "intent_classified"
            flow.context.update(intent.continuation_context)
            flow.last_updated = datetime.now(timezone.utc).isoformat()
            flow.history.append(
                {
                    "step": "intent_classified",
                    "intent": intent.intent_type,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "context": intent.continuation_context,
                }
            )
            return {"conversation_flow": flow}

        return {"conversation_flow": None}


    def _create_error_response(
        self, state: AgentState, error: Exception
    ) -> Dict[str, Any]:
        """
        Create error response.
        
        Args:
            state (AgentState): Current state of the agent.
            error (Exception): Exception encountered.

        Returns:
            Dict[str, Any]: Error intent response.
        """
        error_intent = Intent(
            intent_type="general",
            sub_intent=None,
            confidence=0.1,
            filters=SearchFilter(),
            flow_continuation=False,
            continuation_context={},
        )

        return {
            "rephrased_query": state["current_query"],
            "intent": error_intent,
            "needs_clarification": True,
            "clarification_questions": [
                "Sorry, I encountered an error. Could you rephrase your query?"
            ],
            "flow_analysis": {"error": str(error)},
        }


classify_intent_node = ClassifyIntentNode()
