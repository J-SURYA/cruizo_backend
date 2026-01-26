from datetime import timedelta
import asyncio
from langsmith import traceable


from app.assistant.schema import AgentState, InventorySubIntent, IntentType
from app.services.embedding_services import embedding_service
from app.services.retrieval_services import retrieval_service
from app.schemas.retrieval_schemas import (
    SearchQuery,
    SearchIntent,
    BookingHistoryRequest,
)
from app.core.dependencies import get_sql_session
from app.utils.logger_utils import get_logger
from app.crud import booking_crud


logger = get_logger(__name__)


class InventoryNode:
    """
    Node class for handling inventory-related intents in the agent.
    """
    @traceable(name="process_inventory", run_type="chain")
    async def process_inventory(self, state: AgentState) -> AgentState:
        """
        Process inventory search based on the agent state and intent.

        Args:
            state (AgentState): The current state of the agent.
        
        Returns:
            AgentState: The updated state after processing the inventory intent.
        """
        try:
            intent = state["intent"]
            if intent.intent_type != IntentType.INVENTORY:
                logger.warning(
                    f"Invalid intent for inventory node: {intent.intent_type}"
                )
                return state

            sub_intent = intent.sub_intent
            query = state.get("rephrased_query") or state["current_query"]
            query_embedding = await embedding_service.create_embedding(query)

            search_query = SearchQuery(
                text_query=query,
                query_embedding=query_embedding,
                intent=SearchIntent(
                    intent_type="inventory", confidence=intent.confidence
                ),
                filters=intent.filters,
                top_k=15,
                similarity_threshold=0.25,
            )

            async for db in get_sql_session():
                search_results = await retrieval_service.search(db, search_query)

                if sub_intent == InventorySubIntent.SEMANTIC_SEARCH:
                    state = await self._handle_semantic_search(state, search_results)
                elif sub_intent == InventorySubIntent.CAR_DETAILS:
                    state = await self._handle_car_details(state, search_results)
                elif sub_intent == InventorySubIntent.AVAILABILITY:
                    state = await self._handle_availability(state, search_results, db)
                elif sub_intent == InventorySubIntent.RECOMMENDATION:
                    state = await self._handle_recommendation(state, search_results, db)
                else:
                    state = await self._handle_semantic_search(state, search_results)

            return state

        except Exception as e:
            logger.error(f"Inventory processing failed: {str(e)}", exc_info=True)
            state["llm_response"] = (
                "I encountered an error while searching for cars. Please try again."
            )
            state["metadata"]["error"] = str(e)
            state["suggested_actions"] = [
                {"action": "retry", "label": "Try again"},
                {"action": "contact_support", "label": "Get help"},
            ]
            return state


    async def _handle_semantic_search(
        self, state: AgentState, search_results
    ) -> AgentState:
        """
        Handle semantic search sub-intent.
        
        Args:
            state (AgentState): The current state of the agent.
            search_results: The results from the semantic search.

        Returns:
            AgentState: The updated state after handling semantic search.
        """
        if not search_results.results:
            async for db in get_sql_session():
                popular_cars = await retrieval_service.get_popular_cars(db, limit=7)
                search_results.results = popular_cars
                state["metadata"]["source"] = "popular_cars"
                logger.info(
                    f"No results found, showing {len(popular_cars)} popular cars"
                )
        else:
            state["metadata"]["source"] = "semantic_search"

        state["metadata"]["needs_clarification"] = False
        state["metadata"]["results"] = True
        state["metadata"]["results_count"] = len(search_results.results)
        state["car_embeddings_used"] = [
            {
                "car_id": result.car_id,
                "score": result.score,
                "brand": result.brand,
                "model": result.model,
                "price_per_hour": result.metadata.get("price_per_hour"),
                "metadata": result.metadata,
            }
            for result in search_results.results[:7]
        ]
        state["metadata"]["ask_preferences"] = True
        state["metadata"]["preference_questions"] = [
            "What's your budget per day?",
            "Any specific car type or features you prefer?",
        ]

        return state


    async def _handle_car_details(
        self, state: AgentState, search_results
    ) -> AgentState:
        """
        Handle car details sub-intent with complete information.
        
        Args:
            state (AgentState): The current state of the agent.
            search_results: The results from the semantic search.

        Returns:
            AgentState: The updated state after handling car details.
        """
        if not search_results.results:
            state["metadata"]["results"] = False
            state["metadata"]["needs_clarification"] = True
            state["metadata"]["clarification_questions"] = [
                "What type of car are you looking for?",
                "Do you have any brand or model preferences?",
            ]
        else:
            state["metadata"]["results"] = True
            state["metadata"]["source"] = "semantic_search"

            state["car_embeddings_used"] = [
                {
                    "car_id": car.car_id,
                    "score": car.score,
                    "brand": car.brand,
                    "model": car.model,
                    "price_per_hour": car.metadata.get("price_per_hour"),
                    "metadata": car.metadata,
                }
                for car in search_results.results[:7]
            ]
            state["metadata"]["needs_clarification"] = False
            state["metadata"]["ask_preferences"] = True
            state["metadata"]["preference_questions"] = [
                "What's your budget per day?",
                "How many passengers do you need to seat?",
                "Any specific car type or features you prefer?",
            ]

        state["metadata"]["results_count"] = len(search_results.results)
        return state


    async def _handle_availability(
        self, state: AgentState, search_results, db
    ) -> AgentState:
        """
        Handle availability check with real booking database verification.
        
        Args:
            state (AgentState): The current state of the agent.
            search_results: The results from the semantic search.
            db: The database session for booking checks.
        
        Returns:
            AgentState: The updated state after handling availability.
        """
        intent = state["intent"]
        if (
            not intent.has_dates
            or not intent.extracted_start_date
            or not intent.extracted_end_date
        ):
            state["metadata"]["needs_clarification"] = True
            state["metadata"]["clarification_questions"] = [
                "What are your pickup and drop-off dates?",
                "For how many days do you need the car?",
            ]
            return state

        if not search_results.results:
            state["metadata"]["results"] = False
            state["metadata"]["results_count"] = 0

            state["metadata"]["needs_clarification"] = True
            state["metadata"]["clarification_questions"] = [
                "What type of car are you looking for?",
                "Do you have any brand or model preferences?",
            ]
            return state
        else:
            state["metadata"]["results"] = True
            state["metadata"]["results_count"] = len(search_results.results)
            state["metadata"]["source"] = "semantic_search"

        start_date = intent.extracted_start_date
        end_date = intent.extracted_end_date
        buffer_hours = 4

        start_with_buffer = start_date - timedelta(hours=buffer_hours)
        end_with_buffer = end_date + timedelta(hours=buffer_hours)

        available_cars = []
        unavailable_cars = []

        for result in search_results.results:
            car_id = result.car_id
            is_available = await booking_crud.check_car_availability(
                db, car_id, start_with_buffer, end_with_buffer
            )

            if is_available:
                result.metadata["available"] = True
                available_cars.append(result)
            else:
                next_available = await booking_crud.get_next_available_time(db, car_id)
                result.metadata["available"] = False
                result.metadata["next_available"] = (
                    next_available.isoformat() if next_available else None
                )
                unavailable_cars.append(result)

        if not available_cars:
            state["metadata"]["available_cars"] = False
            state["metadata"]["unavailable_count"] = len(unavailable_cars)
            state["car_embeddings_used"] = [
                {
                    "car_id": result.car_id,
                    "score": result.score,
                    "brand": result.brand,
                    "model": result.model,
                    "price_per_hour": result.metadata.get("price_per_hour"),
                    "metadata": result.metadata,
                }
                for result in unavailable_cars
            ]
        else:
            state["metadata"]["available_cars"] = True
            state["metadata"]["available_count"] = len(available_cars)
            state["metadata"]["checked_for_dates"] = {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            }
            state["car_embeddings_used"] = [
                {
                    "car_id": result.car_id,
                    "score": result.score,
                    "brand": result.brand,
                    "model": result.model,
                    "metadata": result.metadata,
                }
                for result in available_cars
            ]

        state["metadata"]["needs_clarification"] = False
        state["metadata"]["ask_preferences"] = True
        state["metadata"]["preference_questions"] = [
            "What's your budget per day?",
            "What's your preferred car type?",
        ]

        return state


    async def _handle_recommendation(
        self, state: AgentState, search_results, db
    ) -> AgentState:
        """
        Handle recommendation with past booking history analysis.

        Args:
            state (AgentState): The current state of the agent.
            search_results: The results from the semantic search.
            db: The database session for booking checks.

        Returns:
            AgentState: The updated state after handling recommendations.
        """
        user_context = state.get("user_context")
        user_id = None
        if user_context:
            if isinstance(user_context, dict):
                user_id = user_context.get("user_id")
            else:
                user_id = user_context.user_id

        if not user_id:
            logger.warning("No user ID found in context for recommendations")
            return await self._handle_semantic_search(state, search_results)

        try:
            async with asyncio.timeout(8):
                booking_history_request = BookingHistoryRequest(
                    user_id=user_id,
                    recent_bookings_count=5,
                    limit=7,
                    exclude_current_bookings=True,
                )

                history = (
                    await retrieval_service.generate_inventory_from_booking_history(
                        db, booking_history_request
                    )
                )
                if history.recommendations:
                    logger.info(
                        f"Found {len(history.recommendations)} personalized recommendations"
                    )
                    combined_results = self._merge_and_deduplicate_results(
                        history.recommendations, search_results.results, limit=7
                    )
                    search_results.results = combined_results
                    state["metadata"]["source"] = "past_bookings"
                else:
                    async for db in get_sql_session():
                        popular_cars = await retrieval_service.get_popular_cars(
                            db, limit=7
                        )
                        combined_results = self._merge_and_deduplicate_results(
                            popular_cars, search_results.results, limit=7
                        )
                        search_results.results = combined_results
                        state["metadata"]["source"] = "popular_cars"

                state["metadata"]["results"] = True
                state["metadata"]["results_count"] = len(search_results.results)

        except asyncio.TimeoutError:
            logger.warning("Booking history query timed out, using regular results")
        except asyncio.CancelledError:
            logger.warning(f"Booking history query cancelled for user {user_id}")
            raise
        except Exception as e:
            logger.warning(
                f"Could not generate booking history recommendations: {str(e)}"
            )

        if search_results.results:
            state["metadata"]["needs_clarification"] = False
            state["metadata"]["ask_preferences"] = True
            state["metadata"]["preference_questions"] = [
                "What's your budget per day?",
                "How many passengers do you need to seat?",
                "Any specific car type or features you prefer?",
            ]
            state["car_embeddings_used"] = [
                {
                    "car_id": result.car_id,
                    "score": result.score,
                    "brand": result.brand,
                    "model": result.model,
                    "price_per_hour": result.metadata.get("price_per_hour"),
                    "metadata": result.metadata,
                }
                for result in search_results.results
            ]
        else:
            state["metadata"]["results"] = False
            state["metadata"]["needs_clarification"] = True
            state["metadata"]["clarification_questions"] = [
                "What type of car are you looking for?",
                "Do you have any brand or model preferences?",
            ]

        return state


    def _merge_and_deduplicate_results(self, list1, list2, limit=10):
        """
        Merge two lists of SearchResultItem and deduplicate by car_id.

        Args:
            list1: First list of SearchResultItem.
            list2: Second list of SearchResultItem.
            limit: Maximum number of results to return.

        Returns:
            Merged and deduplicated list of SearchResultItem.
        """
        seen_cars = {}
        for result in list1 + list2:
            if hasattr(result, "car_id") and result.car_id:
                if (
                    result.car_id not in seen_cars
                    or result.score > seen_cars[result.car_id].score
                ):
                    seen_cars[result.car_id] = result

        return sorted(seen_cars.values(), key=lambda x: x.score, reverse=True)[:limit]


inventory_node = InventoryNode()
