from langsmith import traceable
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


from app.assistant.schema import AgentState, BookingSubIntent, IntentType
from app.core.dependencies import get_sql_session
from app.core.config import get_settings
from app.utils.logger_utils import get_logger
from app.assistant.tools.sql_tool import sql_query_tool


logger = get_logger(__name__)
settings = get_settings()


class BookingNode:
    """
    Node class that handles booking-related queries using LLM and SQL tool.
    """
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_BASE_URL,
            streaming=False,
            temperature=0.1,
        )


    @traceable(name="process_booking", run_type="chain")
    async def process_booking(self, state: AgentState) -> AgentState:
        """
        Booking processing node that handles booking-related queries using LLM and SQL tool.

        Args:
            state (AgentState): The current state of the agent, including intent and query.

        Returns:
            AgentState: The updated state with booking results or clarification requests.
        """
        try:
            if "metadata" not in state:
                state["metadata"] = {}

            intent = state["intent"]
            if intent.intent_type != IntentType.BOOKING:
                logger.warning(f"Invalid intent for booking node: {intent.intent_type}")
                return state

            sub_intent = intent.sub_intent

            if sub_intent not in [
                BookingSubIntent.BOOKING_HISTORY,
                BookingSubIntent.PAYMENT_HISTORY,
                BookingSubIntent.FREEZE_HISTORY,
            ]:
                state["metadata"]["results"] = False
                state["metadata"]["needs_clarification"] = True
                state["metadata"]["clarification_questions"] = [
                    "This feature is coming soon. Please contact support for assistance."
                ]
                state["booking_results"] = None
                return state

            async for db in get_sql_session():
                state = await self._process_with_llm_tool(state, db)
                break

            return state

        except Exception as e:
            logger.error(f"Booking processing failed: {str(e)}", exc_info=True)
            state["llm_response"] = (
                "I encountered an error while processing your booking request. Please try again."
            )
            state["metadata"]["error"] = str(e)
            state["suggested_actions"] = [
                {"action": "retry", "label": "Try again"},
                {"action": "contact_support", "label": "Contact support"},
            ]
            return state


    async def _process_with_llm_tool(self, state: AgentState, db) -> AgentState:
        """
        Processes the booking request using the LLM and SQL tool to generate and execute SQL queries.
        
        Args:
            state (AgentState): The current state of the agent.
            db: The database session/connection.

        Returns:
            AgentState: The updated state with booking results or clarification requests.
        """
        try:
            user_context = state.get("user_context")
            user_id = None
            if user_context:
                if isinstance(user_context, dict):
                    user_id = user_context.get("user_id")
                else:
                    user_id = user_context.user_id

            if not user_id:
                state["metadata"]["results"] = False
                state["metadata"]["needs_clarification"] = True
                state["metadata"]["clarification_questions"] = [
                    "I couldn't identify your account. Please log in again."
                ]
                state["booking_results"] = None
                return state

            query = state.get("rephrased_query") or state["current_query"]
            intent = state["intent"]
            sub_intent = intent.sub_intent

            system_prompt = self._build_sql_generation_prompt(sub_intent, user_id)

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=query),
            ]

            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "execute_sql_query",
                        "description": "Execute a read-only SQL query against the booking database. Only SELECT queries are allowed.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The SQL SELECT query to execute. Must be a valid SELECT statement with proper JOINs.",
                                },
                                "explanation": {
                                    "type": "string",
                                    "description": "Brief explanation of what the query will retrieve",
                                },
                            },
                            "required": ["query", "explanation"],
                        },
                    },
                }
            ]

            llm_with_tools = self.llm.bind_tools(tools, tool_choice="auto")
            response = await llm_with_tools.ainvoke(messages)

            if response.tool_calls:
                tool_call = response.tool_calls[0]
                function_args = (
                    tool_call.get("args", {})
                    if isinstance(tool_call, dict)
                    else tool_call.args
                )
                sql_query = function_args.get("query")
                explanation = function_args.get("explanation")

                logger.info(f"LLM generated query: {explanation}")

                query_result = await sql_query_tool.execute_query(db, sql_query)

                if query_result["success"]:
                    state["booking_results"] = query_result["results"]
                    state["metadata"]["results"] = True
                    state["metadata"]["results_count"] = query_result["count"]
                    state["metadata"]["source"] = self._map_subintent_to_source(
                        sub_intent
                    )
                    state["metadata"]["needs_clarification"] = False
                    state["metadata"]["sql_query"] = sql_query
                    state["metadata"]["query_explanation"] = explanation
                else:
                    state["metadata"]["results"] = False
                    state["metadata"]["needs_clarification"] = True
                    state["metadata"]["clarification_questions"] = [
                        f"I encountered an error: {query_result.get('error', 'Unknown error')}"
                    ]
                    state["booking_results"] = None
            else:
                if (
                    response.content
                    and "no" in response.content.lower()
                    and "found" in response.content.lower()
                ):
                    state["metadata"]["results"] = False
                    state["metadata"]["needs_clarification"] = True
                    state["metadata"]["clarification_questions"] = [
                        self._get_no_results_message(sub_intent)
                    ]
                    state["booking_results"] = None
                else:
                    state["metadata"]["results"] = False
                    state["metadata"]["needs_clarification"] = True
                    state["metadata"]["clarification_questions"] = [
                        "I couldn't generate a query for your request. Please rephrase."
                    ]
                    state["booking_results"] = None

            return state

        except Exception as e:
            logger.error(f"LLM tool processing failed: {str(e)}", exc_info=True)
            state["metadata"]["results"] = False
            state["metadata"]["error"] = str(e)
            state["booking_results"] = None
            return state


    def _build_sql_generation_prompt(self, sub_intent: str, user_id: str) -> str:
        """
        Builds the system prompt for SQL query generation based on the sub-intent.
        
        Args:
            sub_intent (str): The specific booking sub-intent.
            user_id (str): The user ID for filtering queries.

        Returns:
            str: The constructed system prompt.
        """
        schema_info = sql_query_tool.get_schema_info()

        base_prompt = f"""You are a SQL query generator for a car rental booking system.

{schema_info}

## Your Task

Generate a SELECT query to retrieve the requested booking/payment/freeze information for user_id: '{user_id}'.

## Critical Rules

1. ONLY generate SELECT queries - no CREATE, INSERT, UPDATE, DELETE, DROP, etc.
2. Always filter by the user_id provided: '{user_id}'
3. Use proper JOINs to get complete information
4. Order results by created_at DESC for chronological listing
5. Limit results to 15 records
6. Replace :user_id placeholders with the actual user_id: '{user_id}'

## Query Type: {sub_intent}

"""

        if sub_intent == BookingSubIntent.FREEZE_HISTORY:
            base_prompt += """
### Freeze History Query Requirements

Retrieve all booking freezes for the user with:
- Freeze details (id, dates, expiry, active status)
- Car information (brand, model, color, category)
- Location coordinates (delivery and pickup)

Always include:
- booking_freezes.id
- booking_freezes.start_date
- booking_freezes.end_date
- booking_freezes.freeze_expires_at
- booking_freezes.is_active
- booking_freezes.delivery_latitude
- booking_freezes.delivery_longitude
- booking_freezes.pickup_latitude
- booking_freezes.pickup_longitude
- car details (brand, model, color)
- booking_freezes.created_at

Filter by: booking_freezes.user_id = '{user_id}'
"""

        elif sub_intent == BookingSubIntent.BOOKING_HISTORY:
            base_prompt += """
### Booking History Query Requirements

Retrieve all bookings for the user with:
- Booking details (id, dates, status)
- Car information (brand, model, category, specs)
- Payment summary (from JSONB field)
- Location information
- Status names (booking and payment)

Always include:
- bookings.id
- bookings.start_date
- bookings.end_date
- car details (brand, model, color, transmission, fuel, seats)
- booking status name
- payment status name
- bookings.payment_summary (JSONB)
- location details
- bookings.created_at

Filter by: bookings.booked_by = '{user_id}'
"""

        elif sub_intent == BookingSubIntent.PAYMENT_HISTORY:
            base_prompt += """
### Payment History Query Requirements

Retrieve all payment transactions for the user with:
- Payment details (id, amount, method, type)
- Transaction IDs (transaction_id, razorpay_order_id, razorpay_payment_id)
- Payment status
- Associated booking information
- Car details for context

Always include:
- payments.id
- payments.amount_inr
- payments.payment_method
- payments.payment_type
- payments.transaction_id
- payments.razorpay_order_id
- payments.razorpay_payment_id
- status.name (payment status)
- booking details (car brand, model, dates)
- payments.created_at

Filter by: bookings.booked_by = '{user_id}' (JOIN through bookings table)
"""

        base_prompt += """

## Response Format

If you can generate the query, use the execute_sql_query function with:
- query: The complete SELECT statement
- explanation: Brief description of what it retrieves

If the request is unclear or impossible, respond with text explaining why you cannot generate the query.
"""

        return base_prompt


    def _map_subintent_to_source(self, sub_intent: str) -> str:
        """
        Maps the sub-intent to a source string for metadata.
        
        Args:
            sub_intent (str): The specific booking sub-intent.

        Returns:
            str: The corresponding source string.
        """
        mapping = {
            BookingSubIntent.FREEZE_HISTORY: "freeze_history",
            BookingSubIntent.BOOKING_HISTORY: "booking_history",
            BookingSubIntent.PAYMENT_HISTORY: "payment_history",
        }
        return mapping.get(sub_intent, "booking_query")


    def _get_no_results_message(self, sub_intent: str) -> str:
        """
        Returns a no-results-found message based on the sub-intent.
    
        Args:
            sub_intent (str): The specific booking sub-intent.

        Returns:
            str: The no-results-found message.
        """
        messages = {
            BookingSubIntent.FREEZE_HISTORY: "You don't have any freeze history yet.",
            BookingSubIntent.BOOKING_HISTORY: "You don't have any booking history yet.",
            BookingSubIntent.PAYMENT_HISTORY: "You don't have any payment history yet.",
        }
        return messages.get(sub_intent, "No records found.")


booking_node = BookingNode()
