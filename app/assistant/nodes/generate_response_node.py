from datetime import datetime, timezone
import uuid
import json
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import traceable


from app.assistant.schema import AgentState, Message
from app.assistant.prompts import get_response_prompt
from app.core.config import get_settings
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)
settings = get_settings()


class GenerateResponseNode:
    """
    Node for generating natural language responses using LLM with streaming.
    """
    def __init__(self):
        self.llm = ChatGroq(
            model=settings.GROQ_MODEL,
            api_key=settings.GROQ_API_KEY,
            temperature=0.7,
            streaming=True,
        )


    @traceable(name="generate_response", run_type="llm")
    async def generate_response(self, state: AgentState) -> AgentState:
        """
        Generate response based on intent and search results.

        Args:
            state (AgentState): The current state of the agent.

        Returns:
            AgentState: The updated state after generating the response.
        """
        try:
            system_prompt = get_response_prompt(state["intent"].intent_type)
            user_prompt = self._build_user_prompt(state)

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            response = await self.llm.ainvoke(messages)
            accumulated_response = response.content

            suggested_actions = []
            clean_response = accumulated_response

            try:
                import re

                json_match = re.search(
                    r"```json\s*(\{.*?\})\s*```", accumulated_response, re.DOTALL
                )
                if json_match:
                    json_str = json_match.group(1)
                    parsed_data = json.loads(json_str)
                    suggested_actions = parsed_data.get("suggested_actions", [])
                    clean_response = re.sub(
                        r"```json\s*\{.*?\}\s*```",
                        "",
                        accumulated_response,
                        flags=re.DOTALL,
                    ).strip()
            except Exception as e:
                logger.error(f"Failed to parse suggested_actions: {e}")

            if not suggested_actions:
                intent = state.get("intent")
                if intent:
                    suggested_actions = self._get_default_actions(
                        intent.intent_type, intent.sub_intent
                    )

            state["llm_response"] = clean_response
            state["suggested_actions"] = suggested_actions
            state["metadata"]["streaming"] = False
            state["metadata"]["chunk"] = False
            state["metadata"]["generated_response"] = True

            assistant_message = Message(
                id=str(uuid.uuid4()),
                role="assistant",
                content=clean_response,
                timestamp=datetime.now(timezone.utc),
            )

            if "messages" not in state or state["messages"] is None:
                state["messages"] = []

            existing_ids = {
                msg.id if hasattr(msg, "id") else msg.get("id")
                for msg in state["messages"]
            }
            if assistant_message.id not in existing_ids:
                state["messages"].append(assistant_message)

            return state

        except Exception as e:
            logger.error(f"Response generation failed: {str(e)}", exc_info=True)
            state["llm_response"] = (
                "I apologize, but I encountered an error generating a response. Please try again."
            )
            state["metadata"]["error"] = str(e)
            state["suggested_actions"] = [
                {"action": "retry", "label": "Try again"},
                {"action": "contact_support", "label": "Get help"},
            ]
            return state


    def _get_default_actions(self, intent_type: str, sub_intent: str = None) -> list:
        """
        Get default actions based on intent type and sub-intent.

        Args:
            intent_type (str): The type of intent.
            sub_intent (str, optional): The sub-intent of the intent.

        Returns:
            list: A list of default actions.
        """
        if intent_type == "inventory":
            if sub_intent == "semantic_search":
                return [
                    {"action": "view_details", "label": "View Car Details"},
                    {"action": "book_car", "label": "Book This Car"},
                    {"action": "modify_filters", "label": "Refine Search"},
                ]
            elif sub_intent == "availability":
                return [
                    {"action": "book_car", "label": "Book Now"},
                    {"action": "view_details", "label": "View Details"},
                    {"action": "change_dates", "label": "Try Different Dates"},
                ]
            elif sub_intent == "recommendation":
                return [
                    {"action": "view_details", "label": "View Details"},
                    {"action": "check_availability", "label": "Check Availability"},
                    {"action": "book_car", "label": "Book This Car"},
                ]
            else:
                return [
                    {"action": "view_details", "label": "View Details"},
                    {"action": "search_cars", "label": "Browse Cars"},
                ]

        elif intent_type == "documents":
            if sub_intent == "terms":
                return [
                    {"action": "view_full_terms", "label": "View Full Terms"},
                    {"action": "ask_clarification", "label": "Ask for Clarification"},
                    {"action": "contact_support", "label": "Contact Support"},
                ]
            elif sub_intent == "faq":
                return [
                    {"action": "view_related_faqs", "label": "View Related FAQs"},
                    {"action": "ask_question", "label": "Ask Another Question"},
                    {"action": "contact_support", "label": "Contact Support"},
                ]
            elif sub_intent == "privacy":
                return [
                    {"action": "view_full_policy", "label": "View Full Privacy Policy"},
                    {"action": "ask_clarification", "label": "Ask for Clarification"},
                    {"action": "contact_support", "label": "Contact Support"},
                ]
            elif sub_intent == "help":
                return [
                    {"action": "view_help_article", "label": "View Help Article"},
                    {"action": "ask_question", "label": "Ask Another Question"},
                    {"action": "contact_support", "label": "Contact Support"},
                ]
            else:
                return [
                    {"action": "view_documents", "label": "View Documents"},
                    {"action": "search_faq", "label": "Search FAQ"},
                    {"action": "contact_support", "label": "Contact Support"},
                ]

        elif intent_type == "booking":
            if sub_intent == "freeze_history":
                return [
                    {"action": "make_new_booking", "label": "Make New Booking"},
                    {"action": "contact_support", "label": "Contact Support"},
                ]
            elif sub_intent == "booking_history":
                return [
                    {"action": "view_booking_details", "label": "View Details"},
                    {"action": "make_new_booking", "label": "Make New Booking"},
                    {"action": "contact_support", "label": "Contact Support"},
                ]
            elif sub_intent == "payment_history":
                return [
                    {"action": "view_payment_receipt", "label": "View Receipt"},
                    {"action": "download_invoice", "label": "Download Invoice"},
                    {"action": "contact_support", "label": "Contact Support"},
                ]
            else:
                return [
                    {"action": "make_new_booking", "label": "Make Booking"},
                    {"action": "contact_support", "label": "Contact Support"},
                ]

        elif intent_type == "about":
            return [
                {"action": "search_cars", "label": "Browse Cars"},
                {"action": "view_services", "label": "View Services"},
                {"action": "contact_support", "label": "Contact Us"},
            ]

        elif intent_type == "general":
            return [
                {"action": "search_cars", "label": "Browse Cars"},
                {"action": "view_faq", "label": "View FAQ"},
                {"action": "contact_support", "label": "Contact Support"},
            ]

        else:
            return [
                {"action": "search_cars", "label": "Browse Cars"},
                {"action": "view_faq", "label": "View FAQ"},
                {"action": "contact_support", "label": "Contact Support"},
            ]


    def _format_car_embeddings(self, state: AgentState, max_cars: int = 5) -> str:
        """
        Format car embeddings used in the search results for inclusion in the prompt.
        
        Args:
            state (AgentState): The current state of the agent.
            max_cars (int): Maximum number of cars to include in the formatted output.

        Returns:
            str: Formatted string of car embeddings.
        """
        if not state.get("car_embeddings_used"):
            return ""

        cars_count = len(state["car_embeddings_used"])
        result = [f"\nSearch Results ({cars_count} cars found):\n"]

        for idx, car in enumerate(state["car_embeddings_used"][:max_cars], 1):
            meta = car.get("metadata", {})
            car_summary = [
                f"{idx}. {meta.get('brand', 'Unknown')} {meta.get('model', 'Unknown')}"
            ]

            if meta.get("category"):
                car_summary.append(f"({meta['category']})")

            car_summary.append(f"\n   Price: ₹{meta.get('price_per_day', 0):.0f}/day")

            if meta.get("seats"):
                car_summary.append(f" | Seats: {meta['seats']}")

            if meta.get("transmission"):
                car_summary.append(f" | {meta['transmission']}")

            if meta.get("fuel_type"):
                car_summary.append(f" | {meta['fuel_type']}")

            if meta.get("mileage"):
                car_summary.append(f" | Mileage: {meta['mileage']} km/l")

            if meta.get("color"):
                car_summary.append(f" | Color: {meta['color']}")

            reviews = meta.get("reviews", {})
            if reviews.get("has_reviews"):
                rating = reviews.get("average_rating", 0)
                if rating:
                    car_summary.append(f" | Rating: {rating}/5")

            features = meta.get("features", [])
            if features:
                feature_list = ", ".join(features[:3])
                car_summary.append(f"\n   Features: {feature_list}")

            result.append(" ".join(car_summary) + "\n")

        return "".join(result)


    def _format_document_embeddings(
        self, state: AgentState, metadata: dict, max_docs: int = 5
    ) -> str:
        """
        Format document embeddings used in the search results for inclusion in the prompt.

        Args:
            state (AgentState): The current state of the agent.
            metadata (dict): Metadata related to the document search.
            max_docs (int): Maximum number of documents to include in the formatted output.

        Returns:
            str: Formatted string of document embeddings.
        """
        if not state.get("document_embeddings_used"):
            return ""

        doc_type_labels = {
            "terms": "Terms & Conditions",
            "faq": "FAQ",
            "privacy": "Privacy Policy",
            "help": "Help Centre",
        }

        docs_count = len(state["document_embeddings_used"])
        source = metadata.get("source", "document_search")

        result = [f"\nDocument Results ({docs_count} documents found):\n"]

        for idx, doc in enumerate(state["document_embeddings_used"][:max_docs], 1):
            doc_meta = doc.get("metadata", {})
            doc_type = doc.get("doc_type", "document")
            doc_label = doc_type_labels.get(doc_type, doc_type.title())

            doc_summary = [f"{idx}. {doc_label}"]

            if doc.get("title"):
                doc_summary.append(f" - {doc['title']}")

            doc_summary.append(f"\n   Relevance Score: {doc.get('score', 0):.2f}")

            content = doc.get("content_preview", doc.get("content", ""))
            if content:
                content_preview = (
                    content[:300] + "..." if len(content) > 300 else content
                )
                doc_summary.append(f"\n   Content: {content_preview}")

            if doc_type == "faq" and doc_meta.get("question"):
                doc_summary.append(f"\n   Question: {doc_meta['question']}")

            if doc_meta.get("category"):
                doc_summary.append(f"\n   Category: {doc_meta['category']}")

            result.append(" ".join(doc_summary) + "\n\n")

        return "".join(result)


    def _format_booking_results(self, state: AgentState, metadata: dict) -> str:
        """
        Format booking results for inclusion in the prompt.
        
        Args:
            state (AgentState): The current state of the agent.
            metadata (dict): Metadata related to the booking search.

        Returns:
            str: Formatted string of booking results.
        """
        if not state.get("booking_results"):
            return ""

        source = metadata.get("source", "")
        results_count = len(state["booking_results"])

        result = [f"\nDatabase Query Results ({results_count} records found):\n"]
        result.append(f"Query Type: {source.replace('_', ' ').title()}\n")

        if metadata.get("query_explanation"):
            result.append(f"Query Purpose: {metadata['query_explanation']}\n\n")

        for idx, record in enumerate(state["booking_results"][:10], 1):
            result.append(f"Record {idx}:\n")

            for key, value in record.items():
                if value is not None:
                    if isinstance(value, dict):
                        result.append(f"  {key}: {json.dumps(value, indent=4)}\n")
                    else:
                        result.append(f"  {key}: {value}\n")

            result.append("\n")

        return "".join(result)


    def _build_user_prompt(self, state: AgentState) -> str:
        """
        Build user prompt with context and search results.
        
        Args:
            state (AgentState): The current state of the agent.
        
        Returns:
            str: The constructed user prompt.
        """
        intent = state["intent"]
        metadata = state.get("metadata", {})
        query = state.get("rephrased_query") or state["current_query"]

        prompt_parts = [f"User Query: {query}\n"]
        prompt_parts.append(f"Intent Type: {intent.intent_type}\n")
        prompt_parts.append(f"Sub-Intent: {intent.sub_intent}\n")

        messages_count = len(state.get("messages", []))
        prompt_parts.append(
            f"\nConversation Context: {messages_count} messages in current history\n"
        )

        conversation_summary = state.get("conversation_summary")
        if conversation_summary:
            prompt_parts.append(
                f"\nPrevious Conversation Summary:\n{conversation_summary}\n"
            )
            prompt_parts.append(
                "\nNote: Use this summary to maintain context from earlier parts of the conversation.\n"
            )

        if intent.intent_type == "documents":
            return self._build_documents_prompt(
                state, intent, metadata, prompt_parts
            )
        elif intent.intent_type == "inventory":
            return self._build_inventory_prompt(
                state, intent, metadata, prompt_parts
            )
        elif intent.intent_type == "booking":
            return self._build_booking_prompt(
                state, intent, metadata, prompt_parts
            )
        elif intent.intent_type == "about":
            return self._build_about_prompt(
                state, intent, metadata, prompt_parts
            )
        elif intent.intent_type == "general":
            return self._build_general_prompt(
                state, intent, metadata, prompt_parts
            )
        else:
            return "".join(prompt_parts)


    def _build_documents_prompt(self, state, intent, metadata, prompt_parts):
        """
        Build prompt for document-related queries.
        
        Args:
            state (AgentState): The current state of the agent.
            intent: The intent object containing intent type and sub-intent.
            metadata (dict): Metadata related to the document search.
            prompt_parts (list): List of prompt parts to append to.
        
        Returns:
            str: The constructed document prompt.
        """
        if metadata.get("needs_clarification"):
            prompt_parts.append(
                "\nNo relevant documents found matching the criteria.\n"
            )
            prompt_parts.append("\nUser needs clarification on:\n")
            for question in metadata.get("clarification_questions", []):
                prompt_parts.append(f"- {question}\n")
            prompt_parts.append(
                "\nTask: Politely inform the user, ask the missing information and suggest alternative options."
            )
            prompt_parts.append(
                "\nProvide suggested_actions like: view_documents, search_faq, contact_support"
            )
            return "".join(prompt_parts)

        formatted_docs = self._format_document_embeddings(state, metadata)
        if formatted_docs:
            prompt_parts.append(formatted_docs)

        if intent.sub_intent == "terms":
            prompt_parts.append(
                "\nTask: Present the relevant terms and conditions information clearly."
            )
            prompt_parts.append("\nExplain the key points from the search results.")
            prompt_parts.append(
                "\nProvide suggested_actions like: view_full_terms, ask_clarification, contact_support"
            )

        elif intent.sub_intent == "faq":
            prompt_parts.append(
                "\nTask: Answer the user's question using the FAQ results."
            )
            prompt_parts.append("\nPresent the most relevant Q&A pairs clearly.")
            prompt_parts.append(
                "\nProvide suggested_actions like: view_related_faqs, ask_question, contact_support"
            )

        elif intent.sub_intent == "privacy":
            prompt_parts.append(
                "\nTask: Explain the relevant privacy policy information."
            )
            prompt_parts.append(
                "\nSummarize the key privacy points from the search results."
            )
            prompt_parts.append(
                "\nProvide suggested_actions like: view_full_policy, ask_clarification, contact_support"
            )

        elif intent.sub_intent == "help":
            prompt_parts.append(
                "\nTask: Provide helpful guidance using the help centre articles."
            )
            prompt_parts.append("\nPresent the relevant help information clearly.")
            prompt_parts.append(
                "\nProvide suggested_actions like: view_help_article, ask_question, contact_support"
            )

        else:
            prompt_parts.append(
                "\nTask: Present the relevant document information to answer the user's query."
            )
            prompt_parts.append(
                "\nProvide suggested_actions like: view_documents, search_faq, contact_support"
            )

        return "".join(prompt_parts)


    def _build_inventory_prompt(self, state, intent, metadata, prompt_parts):
        """
        Build prompt for inventory-related queries.

        Args:
            state (AgentState): The current state of the agent.
            intent: The intent object containing intent type and sub-intent.
            metadata (dict): Metadata related to the inventory search.
            prompt_parts (list): List of prompt parts to append to.

        Returns:
            str: The constructed inventory prompt.
        """
        if metadata.get("needs_clarification"):
            prompt_parts.append("\nNo cars found matching the criteria.\n")
            prompt_parts.append("\nUser needs clarification on:\n")
            for question in metadata.get("clarification_questions", []):
                prompt_parts.append(f"- {question}\n")
            prompt_parts.append(
                "\nTask: Politely inform the user, ask the missing information and suggest alternative options."
            )
            prompt_parts.append(
                "\nProvide suggested_actions like: broaden_search, modify_filters, contact_support"
            )
            return "".join(prompt_parts)

        if intent.sub_intent == "semantic_search":
            source = metadata.get("source", "semantic_search")

            if source == "popular_cars":
                prompt_parts.append(
                    "\nNote: Showing popular cars as no specific matches were found."
                )
            prompt_parts.append(
                "\nTask: Present the cars clearly. List top results with key details."
            )
            prompt_parts.append(
                "\nProvide suggested_actions like: view_details, check_availability, book_car"
            )

        elif intent.sub_intent == "car_details":
            prompt_parts.append(
                f"\nTask: Provide detailed information about the cars given below."
            )
            prompt_parts.append(
                "\nProvide suggested_actions like: check_availability, book_car, compare_similar"
            )

        elif intent.sub_intent == "availability":
            if not metadata.get("available_cars"):
                prompt_parts.append(
                    "\nTask: Inform that no cars are available for the selected dates."
                )
                prompt_parts.append(
                    "\nProvide suggested_actions like: change_dates, view_all, modify_filters"
                )
            else:
                available_count = metadata.get("available_count", 0)
                prompt_parts.append(
                    f"\nTask: Inform that {available_count} cars are available."
                )
                prompt_parts.append(
                    "\nTask: Present the cars clearly with key details."
                )
                prompt_parts.append(
                    "\nProvide suggested_actions like: book_car, view_details"
                )

        elif intent.sub_intent == "recommendation":
            recommendation_source = metadata.get("source", "semantic_search")

            prompt_parts.append(
                "\nPresent the cars from car_embeddings_used clearly with key details."
            )
            prompt_parts.append("\nThen, explain the recommendation source: ")
            if recommendation_source == "past_bookings":
                prompt_parts.append(
                    f"\n  - Say: 'Based on your recent bookings, here are top cars...'"
                )
            elif recommendation_source == "popular_cars":
                prompt_parts.append(
                    "\n  - Say: 'Since we couldn't find cars from your recent bookings, here are our most popular and searched cars...'"
                )
            else:
                prompt_parts.append(
                    "\n  - Say: 'Based on your search, here are some great options from our most searched cars...'"
                )

            prompt_parts.append(
                "\nProvide suggested_actions like: view_details, check_availability, book_car"
            )

        else:
            prompt_parts.append(
                "\nTask: Generate a helpful response based on the search results."
            )
            prompt_parts.append("\nProvide 2-4 relevant suggested_actions.")

        formatted_cars = self._format_car_embeddings(state)
        if formatted_cars:
            prompt_parts.append(formatted_cars)

        if metadata.get("ask_preferences"):
            prompt_parts.append("\nFinally: Ask these preference questions")
            for question in metadata.get("preference_questions", []):
                prompt_parts.append(f"\n  - {question}")

        return "".join(prompt_parts)


    def _build_booking_prompt(self, state, intent, metadata, prompt_parts):
        """
        Build prompt for booking-related queries.

        Args:
            state (AgentState): The current state of the agent.
            intent: The intent object containing intent type and sub-intent.
            metadata (dict): Metadata related to the booking search.
            prompt_parts (list): List of prompt parts to append to.

        Returns:
            str: The constructed booking prompt.
        """
        if metadata.get("needs_clarification"):
            prompt_parts.append("\nNo booking records found or missing information.\n")
            prompt_parts.append("\nUser needs clarification on:\n")
            for question in metadata.get("clarification_questions", []):
                prompt_parts.append(f"- {question}\n")
            prompt_parts.append(
                "\nTask: Politely inform the user and provide helpful guidance."
            )
            return "".join(prompt_parts)

        formatted_results = self._format_booking_results(state, metadata)
        if formatted_results:
            prompt_parts.append(formatted_results)

        if intent.sub_intent == "freeze_history":
            prompt_parts.append(
                "\nTask: Present the freeze history in a clear, organized Markdown format."
            )
            prompt_parts.append(
                "\nUse tables for listings and detailed sections for each freeze."
            )
            prompt_parts.append(
                "\nExplain the status of each freeze (active or expired)."
            )
            prompt_parts.append(
                "\nInclude all relevant details: car info, dates, locations."
            )

        elif intent.sub_intent == "booking_history":
            prompt_parts.append(
                "\nTask: Present the booking history with complete details in Markdown format."
            )
            prompt_parts.append(
                "\nUse tables for overview and detailed sections for each booking."
            )
            prompt_parts.append(
                "\nInclude booking status, payment status, car details, and payment summary."
            )
            prompt_parts.append("\nFormat payment amounts properly with ₹ symbol.")

        elif intent.sub_intent == "payment_history":
            prompt_parts.append(
                "\nTask: Present the payment history with transaction details in Markdown format."
            )
            prompt_parts.append(
                "\nUse tables for overview and detailed sections for each payment."
            )
            prompt_parts.append(
                "\nInclude payment status, amounts, transaction IDs, and associated booking info."
            )
            prompt_parts.append(
                "\nFormat transaction IDs in code blocks for easy copying."
            )

        else:
            prompt_parts.append(
                "\nTask: Provide helpful information about the booking request in Markdown format."
            )

        prompt_parts.append(
            "\n\nIMPORTANT: Format your entire response in clean, professional Markdown with:"
        )
        prompt_parts.append("\n- Tables for listings")
        prompt_parts.append("\n- Headers (##, ###) for sections")
        prompt_parts.append(
            "\n- Bold text for important values (IDs, amounts, statuses)"
        )
        prompt_parts.append("\n- Horizontal rules (---) between major sections")
        prompt_parts.append("\n- No emojis")

        return "".join(prompt_parts)


    def _build_about_prompt(self, state, intent, metadata, prompt_parts):
        """
        Build prompt for about queries.
        
        Args:
            state (AgentState): The current state of the agent.
            intent: The intent object containing intent type and sub-intent.
            metadata (dict): Metadata related to the document search.
            prompt_parts (list): List of prompt parts to append to.

        Returns:
            str: The constructed about prompt.
        """
        formatted_docs = self._format_document_embeddings(state, metadata)
        if formatted_docs:
            prompt_parts.append("\nRelevant Context (use sparingly, ~20% weight):")
            prompt_parts.append(formatted_docs)
            prompt_parts.append(
                "\nTask: Provide helpful information about Cruizo primarily from your knowledge."
            )
            prompt_parts.append(
                "\nUse the document context only for supporting details if relevant."
            )
        else:
            prompt_parts.append(
                "\nTask: Provide helpful information about Cruizo from your knowledge."
            )

        prompt_parts.append(
            "\nProvide suggested_actions like: search_cars, view_services, contact_support"
        )

        return "".join(prompt_parts)
    

    def _build_general_prompt(self, state, intent, metadata, prompt_parts):
        """
        Build prompt for general queries.
        
        Args:
            state (AgentState): The current state of the agent.
            intent: The intent object containing intent type and sub-intent.
            metadata (dict): Metadata related to the document search.
            prompt_parts (list): List of prompt parts to append to.

        Returns:
            str: The constructed general prompt.
        """
        sub_intent = intent.sub_intent

        if sub_intent == "greeting":
            prompt_parts.append(
                "\nTask: Respond warmly to the greeting and offer assistance with car rentals."
            )
        elif sub_intent == "chitchat":
            prompt_parts.append(
                "\nTask: Engage briefly in conversation while guiding toward car rental services."
            )
        elif sub_intent == "help_request":
            formatted_docs = self._format_document_embeddings(state, metadata)
            if formatted_docs:
                prompt_parts.append("\nRelevant FAQ Context:")
                prompt_parts.append(formatted_docs)
            prompt_parts.append(
                "\nTask: Provide helpful guidance on how you can assist with car rentals."
            )
        elif sub_intent == "unclear":
            prompt_parts.append(
                "\nTask: Politely ask for clarification while suggesting what you can help with."
            )
        else:
            prompt_parts.append(
                "\nTask: Respond naturally and guide toward car rental services."
            )

        prompt_parts.append(
            "\nProvide suggested_actions like: search_cars, view_faq, contact_support"
        )

        return "".join(prompt_parts)


generate_response_node = GenerateResponseNode()
