import time
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text, Float, Integer, cast, update
from datetime import datetime, timezone
import numpy as np


from app.core.config import get_settings
from app.models.embedding_models import CarEmbedding, DocumentEmbedding
from app.models.booking_models import Booking
from app.models.utility_models import Status
from app.schemas.retrieval_schemas import (
    SearchQuery,
    SearchResponse,
    SearchResultItem,
    BookingHistoryRequest,
    BookingHistoryResponse,
)
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)
settings = get_settings()


class RetrievalService:
    """
    RetrievalService handles semantic search operations for car inventory and documents, as well as generating recommendations based on user booking history.
    """
    async def _apply_car_filters(self, query, filters: Dict[str, Any]):
        """
        Applies various filters to the car embedding query based on the provided filter criteria.
        
        Args:
            query: The base query object to apply filters to
            filters: Dictionary containing filter criteria
        
        Returns:
            Modified query object with applied filters
        """

        conditions = []

        if filters.get("category"):
            conditions.append(
                func.lower(CarEmbedding.meta_data["category"].astext)
                == filters["category"].lower()
            )

        if filters.get("brand"):
            conditions.append(
                func.lower(CarEmbedding.meta_data["brand"].astext)
                == filters["brand"].lower()
            )

        if filters.get("model"):
            conditions.append(
                func.lower(CarEmbedding.meta_data["model"].astext)
                == filters["model"].lower()
            )

        if filters.get("max_price_per_hour"):
            conditions.append(
                cast(CarEmbedding.meta_data["price_per_hour"].astext, Float)
                <= filters["max_price_per_hour"]
            )

        if filters.get("min_price_per_hour"):
            conditions.append(
                cast(CarEmbedding.meta_data["price_per_hour"].astext, Float)
                >= filters["min_price_per_hour"]
            )

        if filters.get("max_price_per_day"):
            conditions.append(
                cast(CarEmbedding.meta_data["price_per_day"].astext, Float)
                <= filters["max_price_per_day"]
            )

        if filters.get("min_price_per_day"):
            conditions.append(
                cast(CarEmbedding.meta_data["price_per_day"].astext, Float)
                >= filters["min_price_per_day"]
            )

        if filters.get("min_seats"):
            conditions.append(
                cast(CarEmbedding.meta_data["seats"].astext, Integer)
                >= filters["min_seats"]
            )

        if filters.get("max_seats"):
            conditions.append(
                cast(CarEmbedding.meta_data["seats"].astext, Integer)
                <= filters["max_seats"]
            )

        if filters.get("fuel_type"):
            conditions.append(
                func.lower(CarEmbedding.meta_data["fuel_type"].astext)
                == filters["fuel_type"].lower()
            )

        if filters.get("transmission"):
            conditions.append(
                func.lower(CarEmbedding.meta_data["transmission"].astext)
                == filters["transmission"].lower()
            )

        if filters.get("color"):
            conditions.append(
                func.lower(CarEmbedding.meta_data["color"].astext)
                == filters["color"].lower()
            )

        if filters.get("features"):
            feature_conditions = []
            for feature in filters["features"]:
                feature_conditions.append(
                    CarEmbedding.meta_data["features"].contains([feature.lower()])
                )
            if feature_conditions:
                conditions.append(or_(*feature_conditions))

        if filters.get("min_year"):
            conditions.append(
                cast(CarEmbedding.meta_data["manufacture_year"].astext, Integer)
                >= filters["min_year"]
            )

        if filters.get("max_year"):
            conditions.append(
                cast(CarEmbedding.meta_data["manufacture_year"].astext, Integer)
                <= filters["max_year"]
            )

        if filters.get("min_mileage"):
            conditions.append(
                cast(CarEmbedding.meta_data["mileage"].astext, Float)
                >= filters["min_mileage"]
            )

        if filters.get("max_mileage"):
            conditions.append(
                cast(CarEmbedding.meta_data["mileage"].astext, Float)
                <= filters["max_mileage"]
            )

        if filters.get("status"):
            conditions.append(
                func.upper(CarEmbedding.meta_data["status"].astext)
                == filters["status"].upper()
            )
        else:
            conditions.append(
                func.upper(CarEmbedding.meta_data["status"].astext) == "ACTIVE"
            )

        if filters.get("days_since_last_service"):
            conditions.append(
                cast(
                    CarEmbedding.meta_data["maintenance"][
                        "last_serviced_days_ago"
                    ].astext,
                    Integer,
                )
                <= filters["days_since_last_service"]
            )

        if filters.get("insurance_valid") is not None:
            conditions.append(
                CarEmbedding.meta_data["maintenance"]["insurance_valid"].astext
                == str(filters["insurance_valid"]).lower()
            )

        if filters.get("pollution_valid") is not None:
            conditions.append(
                CarEmbedding.meta_data["maintenance"]["pollution_valid"].astext
                == str(filters["pollution_valid"]).lower()
            )

        if filters.get("min_avg_rating"):
            conditions.append(
                cast(CarEmbedding.meta_data["reviews"]["average_rating"].astext, Float)
                >= filters["min_avg_rating"]
            )

        if filters.get("min_total_reviews"):
            conditions.append(
                cast(CarEmbedding.meta_data["reviews"]["total_reviews"].astext, Integer)
                >= filters["min_total_reviews"]
            )

        if filters.get("use_cases"):
            use_case_conditions = []
            for use_case in filters["use_cases"]:
                use_case_conditions.append(
                    CarEmbedding.meta_data["use_cases"].contains([use_case.lower()])
                )
            if use_case_conditions:
                conditions.append(or_(*use_case_conditions))

        if conditions:
            query = query.where(and_(*conditions))

        return query


    async def _search_cars_semantic(
        self,
        db: AsyncSession,
        query_embedding: List[float],
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        similarity_threshold: float = 0.4,
    ) -> List[SearchResultItem]:
        """
        Performs a semantic search for cars based on the provided query embedding and optional filters.
        
        Args:
            db: Database session
            query_embedding: Vector embedding of the search query
            filters: Optional dictionary of filter criteria
            top_k: Maximum number of results to return
            similarity_threshold: Minimum similarity score threshold
        
        Returns:
            List of SearchResultItem objects matching the query
        """

        top_k = top_k or settings.TOP_K_RESULTS
        similarity_threshold = similarity_threshold or settings.SIMILARITY_THRESHOLD

        try:
            query = select(
                CarEmbedding,
                (1 - CarEmbedding.embedding.cosine_distance(query_embedding)).label(
                    "similarity"
                ),
            )

            if filters:
                query = await self._apply_car_filters(query, filters)
            else:
                query = query.where(
                    func.upper(CarEmbedding.meta_data["status"].astext) == "ACTIVE"
                )

            query = query.where(
                (1 - CarEmbedding.embedding.cosine_distance(query_embedding))
                >= similarity_threshold
            )
            query = query.order_by(text("similarity DESC")).limit(top_k * 2)

            result = await db.execute(query)
            rows = result.all()

            processed_results = []
            visited_cars = set()
            for car_emb, similarity in rows:
                if len(processed_results) >= top_k:
                    break

                car_id = car_emb.car_id
                if car_id in visited_cars:
                    continue
                visited_cars.add(car_id)
                metadata = car_emb.meta_data or {}

                result_item = SearchResultItem(
                    id=car_emb.id,
                    score=float(similarity),
                    content=car_emb.content,
                    metadata=metadata,
                    doc_type="car",
                    source="semantic_search",
                    car_id=car_id,
                    brand=metadata.get("brand"),
                    model=metadata.get("model"),
                    price_per_hour=metadata.get("price_per_hour"),
                    price_per_day=metadata.get("price_per_day"),
                )
                processed_results.append(result_item)

            if processed_results:
                car_ids = [item.car_id for item in processed_results]
                try:
                    await db.execute(
                        update(CarEmbedding)
                        .where(CarEmbedding.car_id.in_(car_ids))
                        .values(
                            search_count=CarEmbedding.search_count + 1,
                            last_searched_at=datetime.now(timezone.utc),
                        )
                    )
                    await db.commit()
                    logger.info(f"Updated search count for {len(car_ids)} cars")
                except Exception as count_error:
                    logger.warning(f"Failed to update search count: {str(count_error)}")
                    await db.rollback()

            return processed_results

        except Exception as e:
            logger.error(f"Error in car semantic search: {str(e)}", exc_info=True)
            raise


    async def _search_documents_semantic(
        self,
        db: AsyncSession,
        query_embedding: List[float],
        doc_types: Optional[List[str]] = None,
        top_k: int = 10,
        similarity_threshold: float = 0.4,
    ) -> List[SearchResultItem]:
        """
        Performs a semantic search for documents based on the provided query embedding and optional document types.
        
        Args:
            db: Database session
            query_embedding: Vector embedding of the search query
            doc_types: Optional list of document types to filter by
            top_k: Maximum number of results to return
            similarity_threshold: Minimum similarity score threshold
        
        Returns:
            List of SearchResultItem objects matching the query
        """

        top_k = top_k or settings.TOP_K_RESULTS
        similarity_threshold = similarity_threshold or settings.SIMILARITY_THRESHOLD

        try:
            query = select(
                DocumentEmbedding,
                (
                    1 - DocumentEmbedding.embedding.cosine_distance(query_embedding)
                ).label("similarity"),
            )

            if doc_types:
                query = query.where(DocumentEmbedding.doc_type.in_(doc_types))

            query = query.where(
                (1 - DocumentEmbedding.embedding.cosine_distance(query_embedding))
                >= similarity_threshold
            )

            query = query.order_by(text("similarity DESC")).limit(top_k)

            result = await db.execute(query)
            rows = result.all()

            processed_results = []
            for doc_emb, similarity in rows:
                metadata = doc_emb.meta_data or {}

                result_item = SearchResultItem(
                    id=doc_emb.id,
                    score=float(similarity),
                    content=doc_emb.content,
                    metadata=metadata,
                    doc_type=doc_emb.doc_type,
                    source="semantic_search",
                    document_title=doc_emb.title,
                    chunk_index=doc_emb.chunk_index,
                )

                processed_results.append(result_item)

            logger.info(
                f"Document semantic search completed, found {len(processed_results)} results"
            )

            return processed_results

        except Exception as e:
            logger.error(f"Error in document semantic search: {str(e)}", exc_info=True)
            raise


    async def search(
        self, db: AsyncSession, search_query: SearchQuery
    ) -> SearchResponse:
        """
        Executes a search based on the provided search query, handling different intent types such as inventory, documents, or a hybrid of both.
        
        Args:
            db: Database session
            search_query: SearchQuery object containing query parameters and embeddings
        
        Returns:
            SearchResponse object containing search results and metadata
        """

        try:
            filters_dict = (
                search_query.filters.model_dump() if search_query.filters else {}
            )

            if search_query.intent.intent_type == "inventory":
                results = await self._search_cars_semantic(
                    db=db,
                    query_embedding=search_query.query_embedding,
                    filters=filters_dict,
                    top_k=search_query.top_k,
                    similarity_threshold=search_query.similarity_threshold,
                )

            elif search_query.intent.intent_type == "documents":
                doc_types = filters_dict.get(
                    "doc_types", ["terms", "faq", "help", "privacy"]
                )
                results = await self._search_documents_semantic(
                    db=db,
                    query_embedding=search_query.query_embedding,
                    doc_types=doc_types,
                    top_k=search_query.top_k,
                    similarity_threshold=search_query.similarity_threshold,
                )

            elif search_query.intent.intent_type == "hybrid":
                car_percentage = search_query.intent.car_percentage or 0.5
                doc_percentage = search_query.intent.document_percentage or 0.5

                car_top_k = int(search_query.top_k * car_percentage)
                doc_top_k = int(search_query.top_k * doc_percentage)

                car_results = await self._search_cars_semantic(
                    db=db,
                    query_embedding=search_query.query_embedding,
                    filters=filters_dict,
                    top_k=car_top_k,
                    similarity_threshold=search_query.similarity_threshold,
                )

                doc_results = await self._search_documents_semantic(
                    db=db,
                    query_embedding=search_query.query_embedding,
                    doc_types=["terms", "faq", "help", "privacy"],
                    top_k=doc_top_k,
                    similarity_threshold=search_query.similarity_threshold,
                )

                results = car_results + doc_results
                results.sort(key=lambda x: x.score, reverse=True)
                results = results[: search_query.top_k]

            else:
                raise ValueError(
                    f"Unknown intent type: {search_query.intent.intent_type}"
                )

            response = SearchResponse(
                query_id=f"query_{int(time.time())}_{hash(search_query.text_query)}",
                query_text=search_query.text_query,
                intent=search_query.intent,
                total_results=len(results),
                results=results,
                filters_applied=filters_dict,
            )

            logger.info(f"Search completed, found {len(results)} results")

            return response

        except Exception as e:
            logger.error(f"Error in search: {str(e)}", exc_info=True)
            raise


    async def generate_inventory_from_booking_history(
        self, db: AsyncSession, request: BookingHistoryRequest
    ) -> BookingHistoryResponse:
        """
        Generates car inventory recommendations based on the user's recent booking history.
        
        Args:
            db: Database session
            request: BookingHistoryRequest object containing user ID and recommendation parameters
        
        Returns:
            BookingHistoryResponse object containing recommended cars based on booking history
        """

        try:
            recent_bookings_query = (
                select(Booking)
                .where(Booking.booked_by == request.user_id)
                .order_by(Booking.created_at.desc())
                .limit(request.recent_bookings_count)
            )

            result = await db.execute(recent_bookings_query)
            recent_bookings = result.scalars().all()

            if not recent_bookings:
                logger.info(f"No booking history found for user {request.user_id}")
                return BookingHistoryResponse(
                    user_id=request.user_id,
                    recommendations=[],
                    recent_booked_cars=[],
                    recommendation_reason="No booking history available",
                    total_recommendations=0,
                )

            booked_car_ids = [
                booking.car_id for booking in recent_bookings if booking.car_id
            ]

            booked_cars_query = select(CarEmbedding).where(
                CarEmbedding.car_id.in_(booked_car_ids)
            )
            result = await db.execute(booked_cars_query)
            booked_embeddings = result.scalars().all()

            if not booked_embeddings:
                logger.warning(f"No embeddings found for booked cars: {booked_car_ids}")
                return BookingHistoryResponse(
                    user_id=request.user_id,
                    recommendations=[],
                    recent_booked_cars=booked_car_ids,
                    recommendation_reason="No embeddings available for booked cars",
                    total_recommendations=0,
                )

            vectors = []
            for emb in booked_embeddings:
                if hasattr(emb.embedding, "__iter__"):
                    vectors.append(list(emb.embedding))

            if not vectors:
                logger.warning("No valid vectors found for booked cars")
                return BookingHistoryResponse(
                    user_id=request.user_id,
                    recommendations=[],
                    recent_booked_cars=booked_car_ids,
                    recommendation_reason="No valid embedding vectors available",
                    total_recommendations=0,
                )

            avg_vector = np.mean(vectors, axis=0).tolist()

            exclude_ids = booked_car_ids
            if request.exclude_current_bookings:
                current_bookings_query = (
                    select(Booking)
                    .join(Status, Booking.booking_status_id == Status.id)
                    .where(
                        and_(
                            Booking.booked_by == request.user_id,
                            ~Status.name.in_(["DELIVERED", "CANCELLED", "RETURNED"]),
                        )
                    )
                )
                result = await db.execute(current_bookings_query)
                current_bookings = result.scalars().all()
                exclude_ids.extend([b.car_id for b in current_bookings if b.car_id])

            filters_dict = (
                request.additional_filters.model_dump()
                if request.additional_filters
                else {}
            )

            query = select(
                CarEmbedding,
                (1 - CarEmbedding.embedding.cosine_distance(avg_vector)).label(
                    "similarity"
                ),
            ).where(
                and_(
                    CarEmbedding.car_id.notin_(exclude_ids),
                    func.upper(CarEmbedding.meta_data["status"].astext) == "ACTIVE",
                )
            )

            if filters_dict:
                query = await self._apply_car_filters(query, filters_dict)

            query = query.order_by(text("similarity DESC")).limit(request.limit)

            result = await db.execute(query)
            rows = result.all()

            recommendations = []
            for car_emb, similarity in rows:
                if similarity < 0.6:
                    continue

                metadata = car_emb.meta_data or {}

                result_item = SearchResultItem(
                    id=car_emb.id,
                    score=float(similarity),
                    content=car_emb.content,
                    metadata=metadata,
                    doc_type="car",
                    source="booking_history_recommendation",
                    car_id=car_emb.car_id,
                    brand=metadata.get("brand"),
                    model=metadata.get("model"),
                    price_per_hour=metadata.get("price_per_hour"),
                    price_per_day=metadata.get("price_per_day"),
                )

                recommendations.append(result_item)

            if recommendations:
                if len(booked_car_ids) >= 3:
                    reason = f"Based on your {len(booked_car_ids)} recent bookings of similar vehicles"
                else:
                    reason = "Based on your recent booking history"
            else:
                reason = "No suitable recommendations found based on your history"

            logger.info(
                f"Booking history recommendations generated, found {len(recommendations)} recommendations for user {request.user_id}"
            )

            return BookingHistoryResponse(
                user_id=request.user_id,
                recommendations=recommendations,
                recent_booked_cars=booked_car_ids,
                recommendation_reason=reason,
                total_recommendations=len(recommendations),
            )

        except Exception as e:
            logger.error(
                f"Error generating booking history recommendations: {str(e)}",
                exc_info=True,
            )
            raise


    async def get_popular_cars(self, db, limit: int = 10) -> List[SearchResultItem]:
        """
        Retrieves a list of popular cars based on search count and recency of searches.
        
        Args:
            db: Database session
            limit: Maximum number of popular cars to return
        
        Returns:
            List of SearchResultItem objects representing popular cars
        """

        try:
            query = (
                select(CarEmbedding)
                .where(func.upper(CarEmbedding.meta_data["status"].astext) == "ACTIVE")
                .order_by(
                    CarEmbedding.search_count.desc(),
                    CarEmbedding.last_searched_at.desc(),
                )
                .limit(limit)
            )

            result = await db.execute(query)
            embeddings = result.scalars().all()

            popular_cars = []
            for emb in embeddings:
                metadata = emb.meta_data or {}
                popular_cars.append(
                    SearchResultItem(
                        id=emb.id,
                        car_id=emb.car_id,
                        score=0.5,
                        content=emb.content,
                        metadata=metadata,
                        doc_type="car",
                        source="popular_fallback",
                        brand=metadata.get("brand", "Unknown"),
                        model=metadata.get("model", "Unknown"),
                        price_per_hour=metadata.get("price_per_hour"),
                        price_per_day=metadata.get("price_per_day"),
                    )
                )

            logger.info(f"Retrieved {len(popular_cars)} popular cars")
            return popular_cars

        except Exception as e:
            logger.error(f"Failed to get popular cars: {str(e)}")
            return []


    async def search_by_car_ids(
        self, db: AsyncSession, car_ids: List[int], include_metadata: bool = True
    ) -> List[SearchResultItem]:
        """
        Retrieves car embeddings based on a list of car IDs.
        
        Args:
            db: Database session
            car_ids: List of car IDs to retrieve
            include_metadata: Whether to include metadata in the results
        
        Returns:
            List of SearchResultItem objects for the specified car IDs
        """

        try:
            if not car_ids:
                return []

            query = select(CarEmbedding).where(CarEmbedding.car_id.in_(car_ids))

            result = await db.execute(query)
            embeddings = result.scalars().all()

            results = []
            for emb in embeddings:
                metadata = emb.meta_data if include_metadata else {}

                result_item = SearchResultItem(
                    id=emb.id,
                    score=1.0,
                    content=emb.content if include_metadata else "",
                    metadata=metadata,
                    doc_type="car",
                    source="direct_id_lookup",
                    car_id=emb.car_id,
                    brand=metadata.get("brand") if include_metadata else None,
                    model=metadata.get("model") if include_metadata else None,
                    price_per_hour=(
                        metadata.get("price_per_hour") if include_metadata else None
                    ),
                    price_per_day=(
                        metadata.get("price_per_day") if include_metadata else None
                    ),
                )

                results.append(result_item)

            return results

        except Exception as e:
            logger.error(f"Error searching by car IDs: {str(e)}")
            raise


retrieval_service = RetrievalService()
