import asyncio
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from sqlalchemy.orm import selectinload
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from transformers import AutoTokenizer


from app.core.config import get_settings
from app.models import content_models
from app.models.embedding_models import CarEmbedding, DocumentEmbedding
from app.models.car_models import Car, CarModel
from app.schemas import embedding_schemas
from app.utils.logger_utils import get_logger
from app.utils.exception_utils import NotFoundException


logger = get_logger(__name__)
settings = get_settings()


class EmbeddingService:
    """
    Service for creating and managing text embeddings for car rental platform.
    """
    def __init__(self):
        self.model = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION

        self.hf_embeddings = HuggingFaceEmbeddings(
            model_name=self.model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

        # Stage 1: Semantic chunking
        self.semantic_chunker = SemanticChunker(
            embeddings=self.hf_embeddings,
            breakpoint_threshold_type=settings.SEMANTIC_BREAKPOINT_TYPE,
            breakpoint_threshold_amount=settings.SEMANTIC_BREAKPOINT_THRESHOLD,
        )

        # Stage 2: Token-aware size limiting
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model)
        except Exception as e:
            logger.warning(
                f"Could not load tokenizer for {self.model}: {e}. Falling back to character-based splitting."
            )
            self.tokenizer = None

        def token_length(text: str) -> int:
            if self.tokenizer is None:
                return len(text)
            return len(self.tokenizer.encode(text, add_special_tokens=False))

        self.recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=token_length,
        )

    async def create_embedding(self, text: str) -> List[float]:
        """
        Creates an embedding for a single text string.
        
        Args:
            text: The text string to create an embedding for
        
        Returns:
            List of floats representing the embedding vector
        """
        try:
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, self.hf_embeddings.embed_query, text
            )
            return embedding
        except Exception as e:
            logger.error(f"Error creating embedding: {str(e)}")
            raise


    async def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Creates embeddings for a batch of text strings.
        
        Args:
            texts: List of text strings to create embeddings for
        
        Returns:
            List of embedding vectors, one for each input text
        """
        try:
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None, self.hf_embeddings.embed_documents, texts
            )
            return embeddings
        except Exception as e:
            logger.error(f"Error creating batch embeddings: {str(e)}")
            raise


    def chunk_text(self, text: str) -> List[str]:
        """
        Splits the input text into smaller chunks based on semantic and token-aware criteria.
        
        Args:
            text: The input text to split into chunks
        
        Returns:
            List of text chunks
        """
        chunks = []
        for chunk in [text]:
            chunks.extend(self.recursive_splitter.split_text(chunk))
        return chunks


    async def delete_car_embedding(self, db: AsyncSession, car_id: int) -> bool:
        """
        Deletes the embedding associated with a specific car.
        
        Args:
            db: Database session
            car_id: ID of the car whose embedding should be deleted
        
        Returns:
            True if embedding was deleted, False otherwise
        """
        try:
            query = delete(CarEmbedding).where(CarEmbedding.car_id == car_id)
            result = await db.execute(query)
            await db.commit()

            deleted = result.rowcount > 0
            if deleted:
                logger.info(f"Deleted embedding for car {car_id}")
            return deleted

        except Exception as e:
            await db.rollback()
            logger.error(f"Error deleting car embedding: {str(e)}")
            raise


    def _calculate_content_hash(self, content: str) -> str:
        """
        Calculate hash of content to detect changes.
        
        Args:
            content: The content string to hash
        
        Returns:
            SHA256 hash of the content
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


    def _generate_car_description(self, car: Car) -> str:
        """
        Generate comprehensive car description for embedding.
        
        Args:
            car: Car object with related entities loaded
        
        Returns:
            Comprehensive text description of the car
        """

        description_parts = []
        if car.car_model:
            description_parts.append(
                f"The {car.manufacture_year} {car.car_model.brand} {car.car_model.model}"
            )

            if car.car_model.category:
                description_parts.append(f"is a {car.car_model.category.category_name}")

            if car.car_model.capacity:
                description_parts.append(
                    f"with seating for {car.car_model.capacity.capacity_value} passengers"
                )

        tech_specs = []
        if car.car_model:
            tech_specs.append(f"{car.car_model.transmission_type.value} transmission")

            if car.car_model.fuel:
                tech_specs.append(f"{car.car_model.fuel.fuel_name} engine")

            tech_specs.append(f"{car.car_model.mileage} km/l fuel efficiency")

        if tech_specs:
            description_parts.append(f"It features {', '.join(tech_specs)}.")

        if car.car_model and car.car_model.features:
            features = [f.feature_name for f in car.car_model.features]
            if features:
                description_parts.append(
                    f"Key features include: {', '.join(features[:10])}"
                    + (
                        f" and {len(features)-10} more features"
                        if len(features) > 10
                        else ""
                    )
                )

        appearance_parts = []
        if car.color:
            appearance_parts.append(f"{car.color.color_name} exterior")

        if car.car_no:
            appearance_parts.append(f"vehicle number {car.car_no}")

        if appearance_parts:
            description_parts.append(f"This car has {', '.join(appearance_parts)}.")

        if car.car_model:
            rental_parts = [
                f"${car.car_model.rental_per_hr:.2f} per hour",
                f"${car.car_model.rental_per_hr * 24:.2f} daily rate",
            ]

            if car.car_model.kilometer_limit_per_hr:
                rental_parts.append(
                    f"{car.car_model.kilometer_limit_per_hr} km per hour limit"
                )

            description_parts.append(f"Rental details: {', '.join(rental_parts)}.")

        if car.status:
            status_desc = (
                "available for rent"
                if car.status.name.lower() == "active"
                else car.status.name
            )
            description_parts.append(f"Currently {status_desc}.")

        maintenance_parts = []

        if car.last_serviced_date:
            days_since = (datetime.now(timezone.utc) - car.last_serviced_date).days
            if days_since == 0:
                maintenance_parts.append("serviced today")
            elif days_since < 7:
                maintenance_parts.append(f"serviced {days_since} days ago")
            elif days_since < 30:
                maintenance_parts.append(f"serviced {days_since//7} weeks ago")
            else:
                maintenance_parts.append(f"serviced {days_since//30} months ago")

        if car.service_frequency_months:
            maintenance_parts.append(
                f"service every {car.service_frequency_months} months"
            )

        expiry_info = []
        current_time = datetime.now(timezone.utc)

        if car.insured_till:
            days_left = (car.insured_till - current_time).days
            if days_left > 0:
                expiry_info.append(f"insurance valid for {days_left} days")
            else:
                expiry_info.append("insurance requires renewal")

        if car.pollution_expiry:
            days_left = (car.pollution_expiry - current_time).days
            if days_left > 0:
                expiry_info.append(f"pollution certificate valid for {days_left} days")
            else:
                expiry_info.append("pollution certificate requires renewal")

        if expiry_info:
            maintenance_parts.append(f"Documents: {', '.join(expiry_info)}")

        if maintenance_parts:
            description_parts.append(f"Maintenance: {', '.join(maintenance_parts)}.")

        if hasattr(car, "reviews") and car.reviews:
            valid_reviews = [
                r
                for r in car.reviews
                if hasattr(r, "remarks") and r.remarks and r.remarks.strip()
            ]
            if valid_reviews:
                sorted_reviews = sorted(
                    valid_reviews,
                    key=lambda r: (
                        r.created_at if hasattr(r, "created_at") else datetime.min
                    ),
                    reverse=True,
                )[:5]

                if sorted_reviews:
                    review_summary = []
                    for review in sorted_reviews:
                        if hasattr(review, "remarks") and review.remarks:
                            remarks = review.remarks.strip()
                            if len(remarks) > 100:
                                remarks = remarks[:100] + "..."

                            rating = getattr(review, "rating", None)
                            rating_info = f" ({rating}/5)" if rating is not None else ""
                            review_summary.append(f'"{remarks}"{rating_info}')

                    if review_summary:
                        description_parts.append(
                            f"Recent customer feedback includes: {'; '.join(review_summary)}."
                        )
            else:
                description_parts.append("No recent customer reviews available.")
        else:
            description_parts.append("No recent customer reviews available.")

        use_cases = self._infer_use_cases(car)
        if use_cases:
            description_parts.append(f"Ideal for: {', '.join(use_cases)}.")

        return " ".join(description_parts)


    def _infer_use_cases(self, car: Car) -> List[str]:
        """
        Infer use cases based on car attributes.
        
        Args:
            car: Car object to infer use cases for
        
        Returns:
            List of use case strings
        """
        use_cases = []

        if not car.car_model:
            return use_cases

        if car.car_model.category:
            category_lower = car.car_model.category.category_name.lower()
            if any(x in category_lower for x in ["suv", "crossover"]):
                use_cases.extend(["family trips", "road trips", "off-road adventures"])
            elif any(x in category_lower for x in ["sedan", "saloon"]):
                use_cases.extend(
                    ["business travel", "city commuting", "comfortable rides"]
                )
            elif any(x in category_lower for x in ["hatchback", "compact"]):
                use_cases.extend(
                    [
                        "city driving",
                        "parking in tight spaces",
                        "fuel-efficient commuting",
                    ]
                )
            elif any(x in category_lower for x in ["electic", "ev"]):
                use_cases.extend(["urban commuting", "zero-emission travel"])

        if car.car_model.capacity:
            seats = car.car_model.capacity.capacity_value
            if seats >= 7:
                use_cases.append("large groups")
            elif seats >= 5:
                use_cases.append("family outings")

        if car.car_model.features:
            features_lower = [f.feature_name.lower() for f in car.car_model.features]
            if any(x in features_lower for x in ["luxury", "premium", "leather"]):
                use_cases.append("luxury travel")
            if any(x in features_lower for x in ["safety", "airbag", "assist"]):
                use_cases.append("safe family transportation")
            if any(x in features_lower for x in ["gps", "navigation", "entertainment"]):
                use_cases.append("long distance travel")

        if car.car_model.fuel:
            fuel_lower = car.car_model.fuel.fuel_name.lower()
            if "electric" in fuel_lower:
                use_cases.append("eco-friendly driving")
            elif "diesel" in fuel_lower:
                use_cases.append("long highway drives")

        return list(dict.fromkeys(use_cases))


    def _generate_car_metadata(self, car: Car) -> Dict[str, Any]:
        """
        Generate structured metadata for filtering and display.
        
        Args:
            car: Car object to generate metadata for
        
        Returns:
            Dictionary containing structured metadata
        """

        metadata = {
            "car_id": car.id,
            "car_no": car.car_no,
            "doc_type": "car",
            "embedding_version": "1.0",
            "content_hash": None,
        }

        if car.car_model:
            metadata.update(
                {
                    "brand": car.car_model.brand.lower(),
                    "model": car.car_model.model.lower(),
                    "manufacture_year": car.manufacture_year,
                }
            )

            if car.car_model.category:
                metadata["category"] = car.car_model.category.category_name.lower()

            if car.car_model.capacity:
                metadata["seats"] = car.car_model.capacity.capacity_value

            if car.car_model.fuel:
                metadata["fuel_type"] = car.car_model.fuel.fuel_name.lower()

            metadata["transmission"] = car.car_model.transmission_type.value.lower()
            metadata["mileage"] = car.car_model.mileage

            metadata.update(
                {
                    "price_per_hour": float(car.car_model.rental_per_hr),
                    "price_per_day": float(car.car_model.rental_per_hr * 24),
                    "kilometer_limit_per_hour": car.car_model.kilometer_limit_per_hr,
                }
            )

            if car.car_model.features:
                metadata["features"] = [
                    f.feature_name.lower() for f in car.car_model.features
                ]

        if car.color:
            metadata["color"] = car.color.color_name.lower()

        if car.status:
            metadata["status"] = car.status.name.lower()
            metadata["available"] = car.status.name.lower() in ["active", "available"]

        maintenance_info = {}
        if car.last_serviced_date:
            maintenance_info["last_serviced_date"] = car.last_serviced_date.isoformat()
            maintenance_info["last_serviced_days_ago"] = (
                datetime.now(timezone.utc) - car.last_serviced_date
            ).days

        if car.service_frequency_months:
            maintenance_info["service_frequency_months"] = car.service_frequency_months

        current_time = datetime.now(timezone.utc)

        if car.insured_till:
            days_left = (car.insured_till - current_time).days
            maintenance_info["insurance_expiry_days"] = days_left
            maintenance_info["insurance_valid"] = days_left > 0

        if car.pollution_expiry:
            days_left = (car.pollution_expiry - current_time).days
            maintenance_info["pollution_expiry_days"] = days_left
            maintenance_info["pollution_valid"] = days_left > 0

        if maintenance_info:
            metadata["maintenance"] = maintenance_info

        reviews_data = {"has_reviews": False, "message": "No reviews available."}

        if hasattr(car, "reviews") and car.reviews:
            valid_reviews = [
                r
                for r in car.reviews
                if hasattr(r, "remarks") and r.remarks and r.remarks.strip()
            ]

            if valid_reviews:
                ratings = [
                    r.rating for r in valid_reviews if hasattr(r, "rating") and r.rating
                ]

                if ratings:
                    avg_rating = sum(ratings) / len(ratings)

                    sorted_reviews = sorted(
                        valid_reviews,
                        key=lambda r: (
                            r.created_at if hasattr(r, "created_at") else datetime.min
                        ),
                        reverse=True,
                    )[:5]

                    recent_reviews = []
                    for review in sorted_reviews:
                        if hasattr(review, "remarks") and review.remarks:
                            review_data = {
                                "rating": (
                                    review.rating if hasattr(review, "rating") else None
                                ),
                                "comment_preview": (
                                    review.remarks[:50] + "..."
                                    if len(review.remarks) > 50
                                    else review.remarks
                                ),
                                "date": (
                                    review.created_at.isoformat()
                                    if hasattr(review, "created_at")
                                    and review.created_at
                                    else None
                                ),
                            }
                            recent_reviews.append(review_data)

                    reviews_data = {
                        "has_reviews": True,
                        "average_rating": round(avg_rating, 1),
                        "total_reviews": len(valid_reviews),
                        "recent_reviews_count": len(recent_reviews),
                        "recent_reviews": recent_reviews if recent_reviews else None,
                        "rating_breakdown": {
                            str(i): sum(1 for r in ratings if r == i)
                            for i in range(1, 6)
                        },
                    }
                else:
                    reviews_data = {
                        "has_reviews": False,
                        "message": "No reviews with ratings available.",
                    }
        metadata["reviews"] = reviews_data
        use_cases = self._infer_use_cases(car)
        if use_cases:
            metadata["use_cases"] = use_cases

        if hasattr(car, "image_urls") and car.image_urls:
            metadata["image_count"] = len(car.image_urls)
            if car.image_urls:
                metadata["primary_image"] = car.image_urls[0]

        return metadata


    async def _load_car_with_relations(
        self, db: AsyncSession, car_id: int
    ) -> Optional[Car]:
        """
        Load car with all related entities for embedding generation.
        
        Args:
            db: Database session
            car_id: ID of the car to load
        
        Returns:
            Car object with all relations loaded, or None if not found
        """

        query = (
            select(Car)
            .options(
                selectinload(Car.car_model).selectinload(CarModel.category),
                selectinload(Car.car_model).selectinload(CarModel.fuel),
                selectinload(Car.car_model).selectinload(CarModel.capacity),
                selectinload(Car.car_model).selectinload(CarModel.features),
                selectinload(Car.color),
                selectinload(Car.status),
                selectinload(Car.reviews),
            )
            .where(Car.id == car_id)
        )

        result = await db.execute(query)
        car = result.scalar_one_or_none()
        if not car:
            raise NotFoundException(f"Car with id {car_id} not found")
        return car


    async def _embed_car_object(
        self, db: AsyncSession, car: Car, force_refresh: bool = False
    ) -> embedding_schemas.CarEmbeddingResponse:
        """
        Creates or updates the embedding for a given car object.
        
        Args:
            db: Database session
            car: Car object to create embedding for
            force_refresh: Whether to force refresh even if content unchanged
        
        Returns:
            CarEmbeddingResponse containing the embedding data
        """

        try:
            car_id = car.id

            query = select(CarEmbedding).where(CarEmbedding.car_id == car_id)
            result = await db.execute(query)
            existing = result.scalar_one_or_none()

            content = self._generate_car_description(car)
            content_hash = self._calculate_content_hash(content)
            metadata = self._generate_car_metadata(car)
            metadata["content_hash"] = content_hash

            if existing and not force_refresh:
                existing_metadata = existing.meta_data or {}
                existing_hash = existing_metadata.get("content_hash")

                if existing_hash == content_hash:
                    logger.info(f"Embedding up-to-date for car {car_id}")
                    return embedding_schemas.CarEmbeddingResponse.model_validate(
                        existing
                    )

            embedding_vector = await self.create_embedding(content)
            current_time = datetime.now(timezone.utc)
            if existing:
                await db.execute(
                    update(CarEmbedding)
                    .where(CarEmbedding.id == existing.id)
                    .values(
                        content=content,
                        embedding=embedding_vector,
                        meta_data=metadata,
                        updated_at=current_time,
                    )
                )
                await db.commit()
                await db.refresh(existing)
                logger.info(f"Updated embedding for car {car_id}")
                return embedding_schemas.CarEmbeddingResponse.model_validate(existing)
            else:
                car_embedding = CarEmbedding(
                    car_id=car_id,
                    content=content,
                    embedding=embedding_vector,
                    meta_data=metadata,
                    created_at=current_time,
                    updated_at=current_time,
                )
                db.add(car_embedding)
                await db.commit()
                await db.refresh(car_embedding)

                logger.info(f"Created embedding for car {car_id}")
                return embedding_schemas.CarEmbeddingResponse.model_validate(
                    car_embedding
                )

        except Exception as e:
            await db.rollback()
            try:
                car_id = getattr(car, "id", "unknown")
            except Exception:
                car_id = "unknown"
            logger.error(f"Error embedding car {car_id}: {str(e)}")
            raise


    async def embed_car(
        self, db: AsyncSession, car_id: int, force_refresh: bool = False
    ) -> embedding_schemas.CarEmbeddingResponse:
        """
        Embeds a single car by its ID, optionally forcing a refresh of the embedding.
        
        Args:
            db: Database session
            car_id: ID of the car to embed
            force_refresh: Whether to force refresh even if content unchanged
        
        Returns:
            CarEmbeddingResponse containing the embedding data
        """

        try:
            stmt = select(Car).where(Car.id == car_id)
            result = await db.execute(stmt)
            car = result.scalar_one_or_none()

            if not car:
                raise NotFoundException(f"Car with id {car_id} not found")

            car = await self._load_car_with_relations(db, car_id)
            return await self._embed_car_object(db, car, force_refresh)

        except Exception as e:
            await db.rollback()
            logger.error(f"Error embedding car {car_id}: {str(e)}")
            raise


    async def embed_all_cars(
        self, db: AsyncSession, batch_size: int = 50, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Embeds all cars in the database in batches, optionally forcing a refresh of embeddings.
        
        Args:
            db: Database session
            batch_size: Number of cars to process in each batch
            force_refresh: Whether to force refresh even if content unchanged
        
        Returns:
            Dictionary with batch processing statistics
        """
        try:
            query = select(Car).options(
                selectinload(Car.car_model).selectinload(CarModel.category),
                selectinload(Car.car_model).selectinload(CarModel.fuel),
                selectinload(Car.car_model).selectinload(CarModel.capacity),
                selectinload(Car.car_model).selectinload(CarModel.features),
                selectinload(Car.color),
                selectinload(Car.status),
                selectinload(Car.reviews),
            )

            result = await db.execute(query)
            cars = result.scalars().all()

            total_cars = len(cars)
            processed = 0
            errors = 0
            failed_car_ids = []

            for i in range(0, total_cars, batch_size):
                batch = cars[i : i + batch_size]
                for car in batch:
                    try:
                        await self._embed_car_object(db, car, force_refresh)
                        processed += 1
                    except Exception as e:
                        car_id = getattr(car, "id", "unknown")
                        logger.error(f"Error processing car {car_id}: {str(e)}")
                        errors += 1
                        try:
                            failed_car_ids.append(car_id)
                        except Exception:
                            pass

            success_rate = processed / total_cars if total_cars > 0 else 0

            logger.info(f"Embedded {processed}/{total_cars} cars with {errors} errors.")

            return embedding_schemas.BatchEmbeddingResult(
                total_cars=total_cars,
                processed=processed,
                errors=errors,
                success_rate=success_rate,
                failed_car_ids=failed_car_ids if failed_car_ids else None,
            )

        except Exception as e:
            logger.error(f"Error in batch embedding: {str(e)}")
            raise


    def _extract_text_from_content(self, content) -> str:
        """
        Extracts plain text from various content types for embedding.
        
        Args:
            content: Content object with type attribute
        
        Returns:
            Extracted plain text string
        """
        if not content or not hasattr(content, "type"):
            return ""

        try:
            if content.type == "text":
                return content.text or ""
            elif content.type == "qa" and content.qa:
                question = (
                    content.qa.get("question", "")
                    if isinstance(content.qa, dict)
                    else ""
                )
                answer = (
                    content.qa.get("answer", "") if isinstance(content.qa, dict) else ""
                )
                return f"Q: {question}\nA: {answer}"
            elif content.type == "table" and content.table:
                if not isinstance(content.table, dict):
                    return ""

                rows = []
                columns = content.table.get("columns", [])
                if columns:
                    rows.append(" | ".join(str(col) for col in columns))

                table_rows = content.table.get("rows", [])
                for row in table_rows:
                    if isinstance(row, list):
                        rows.append(" | ".join(str(cell) for cell in row))

                return "\n".join(rows) if rows else ""
            return ""

        except Exception as e:
            logger.warning(f"Error extracting text from content: {str(e)}")
            return ""


    async def _embed_document_content_with_vector(
        self,
        db: AsyncSession,
        doc_type: str,
        master_id: int,
        section_title: str,
        content: str,
        embedding_vector: List[float],
        chunk_index: int,
        total_chunks: int,
        metadata: Dict[str, Any],
    ) -> embedding_schemas.DocumentEmbeddingResponse:
        """
        Creates or updates a document embedding record with the provided embedding vector and metadata.
        
        Args:
            db: Database session
            doc_type: Type of document (terms, faq, help, privacy)
            master_id: ID of the master document
            section_title: Title of the section
            content: Text content to embed
            embedding_vector: Pre-computed embedding vector
            chunk_index: Index of this chunk in the document
            total_chunks: Total number of chunks in the document
            metadata: Additional metadata dictionary
        
        Returns:
            DocumentEmbeddingResponse containing the embedding data
        """
        try:
            doc_id = f"{doc_type}_{master_id}_{chunk_index}"
            doc_metadata = {
                "doc_type": doc_type,
                "master_id": master_id,
                "section_title": section_title,
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "created_at": datetime.now(timezone.utc).isoformat(),
                **metadata,
            }

            query = select(DocumentEmbedding).where(
                DocumentEmbedding.doc_id == doc_id,
                DocumentEmbedding.doc_type == doc_type,
            )
            existing_result = await db.execute(query)
            existing = existing_result.scalar_one_or_none()
            current_time = datetime.now(timezone.utc)

            if existing:
                existing.content = content
                existing.embedding = embedding_vector
                existing.meta_data = doc_metadata
                existing.title = section_title[:500]
                existing.updated_at = current_time

                await db.commit()
                await db.refresh(existing)

                logger.debug(f"Updated embedding for {doc_type} chunk {chunk_index}")
                return embedding_schemas.DocumentEmbeddingResponse.model_validate(
                    existing
                )
            else:
                doc_embedding = DocumentEmbedding(
                    doc_type=doc_type,
                    doc_id=doc_id,
                    title=section_title[:500],
                    chunk_index=chunk_index,
                    content=content,
                    embedding=embedding_vector,
                    meta_data=doc_metadata,
                    created_at=current_time,
                    updated_at=current_time,
                )

                db.add(doc_embedding)
                await db.commit()
                await db.refresh(doc_embedding)
                return embedding_schemas.DocumentEmbeddingResponse.model_validate(
                    doc_embedding
                )

        except Exception as e:
            logger.error(f"Error creating document embedding record: {str(e)}")
            raise


    async def _embed_terms(
        self, db: AsyncSession, terms: content_models.TermsMaster
    ) -> int:
        """
        Embeds the terms and conditions document by processing its sections and contents.
        
        Args:
            db: Database session
            terms: TermsMaster object containing sections and contents
        
        Returns:
            Number of chunks embedded
        """
        count = 0
        chunk_index = 0

        for section in terms.sections:
            section_text_parts = []

            for content in section.contents:
                text = self._extract_text_from_content(content)
                if content.type == "text":
                    section_text_parts.append(f"Information: {text}")
                elif content.type == "qa":
                    section_text_parts.append(f"Q&A: {text}")
                elif content.type == "table":
                    section_text_parts.append(f"Table: {text}")

            if not section_text_parts:
                continue

            full_text = f"""
            Terms & Conditions
            Section: {section.title}
            {chr(10).join(section_text_parts)}
            """

            chunks = self.chunk_text(full_text)

            if not chunks:
                continue

            chunked_embeddings = await self.create_embeddings_batch(chunks)
            for chunk_idx, (chunk, embedding) in enumerate(
                zip(chunks, chunked_embeddings)
            ):
                try:
                    await self._embed_document_content_with_vector(
                        db=db,
                        doc_type="terms",
                        master_id=terms.id,
                        section_title=section.title,
                        content=chunk,
                        embedding_vector=embedding,
                        chunk_index=chunk_index,
                        total_chunks=len(chunks),
                        metadata={
                            "section_id": section.id,
                            "section_order": section.order,
                            "local_chunk_index": chunk_idx,
                            "content_type": "terms",
                            "version": f"v{terms.id}",
                            "effective_from": (
                                terms.effective_from.isoformat()
                                if terms.effective_from
                                else None
                            ),
                            "is_active": terms.is_active,
                            "tags": ["legal", "terms", "conditions"],
                        },
                    )
                    count += 1
                    chunk_index += 1

                except Exception as e:
                    logger.error(f"Error embedding terms chunk {chunk_idx}: {str(e)}")
                    continue

        logger.info(f"Embedded {count} chunks from Terms & Conditions v{terms.id}")
        return count


    async def _embed_faq(self, db: AsyncSession, faq: content_models.FAQMaster) -> int:
        """
        Embeds the FAQ document by processing its sections and contents.
        
        Args:
            db: Database session
            faq: FAQMaster object containing sections and contents
        
        Returns:
            Number of chunks embedded
        """
        count = 0
        chunk_index = 0

        for section in faq.sections:
            for content in section.contents:
                if content.type == "qa" and content.qa:
                    text = self._extract_text_from_content(content)
                    if not text or not text.strip():
                        continue
                    text = f"""
                    Faq-Q&A
                    Topic: {section.title}
                    {text}
                    """
                    question = ""
                    if isinstance(content.qa, dict):
                        question = content.qa.get("question", "")[:200]

                    chunks = self.chunk_text(text)

                    if not chunks:
                        continue

                    embeddings = await self.create_embeddings_batch(chunks)

                    for chunk_idx, (chunk, embedding) in enumerate(
                        zip(chunks, embeddings)
                    ):
                        try:
                            await self._embed_document_content_with_vector(
                                db=db,
                                doc_type="faq",
                                master_id=faq.id,
                                section_title=section.title,
                                content=chunk,
                                embedding_vector=embedding,
                                chunk_index=chunk_index,
                                total_chunks=len(chunks),
                                metadata={
                                    "section_id": section.id,
                                    "content_id": content.id,
                                    "content_order": content.order,
                                    "content_type": "qa",
                                    "question": question,
                                    "category": section.title,
                                    "is_active": faq.is_active,
                                    "is_qa": True,
                                    "tags": [
                                        "faq",
                                        "help",
                                        section.title.lower().replace(" ", "_"),
                                    ],
                                },
                            )
                            count += 1
                            chunk_index += 1
                        except Exception as e:
                            logger.error(
                                f"Error embedding FAQ Q&A chunk {chunk_idx}: {str(e)}"
                            )
                            continue

        logger.info(f"Embedded {count} chunks from FAQ v{faq.id}")
        return count


    async def _embed_help_centre(
        self, db: AsyncSession, help_centre: content_models.HelpCentreMaster
    ) -> int:
        """
        Embeds the help centre document by processing its sections and contents.
        
        Args:
            db: Database session
            help_centre: HelpCentreMaster object containing sections and contents
        
        Returns:
            Number of chunks embedded
        """
        count = 0
        chunk_index = 0

        for section in help_centre.sections:
            section_text_parts = []

            for content in section.contents:
                text = self._extract_text_from_content(content)
                if text and text.strip():
                    if content.type == "text":
                        section_text_parts.append(f"Help: {text}")
                    elif content.type == "qa":
                        section_text_parts.append(f"Q&A Help: {text}")
                    elif content.type == "table":
                        section_text_parts.append(f"Reference Table: {text}")

            if not section_text_parts:
                continue
            full_text = f"""
            Help Centre
            Topic: {section.title}
            {chr(10).join(section_text_parts)}
            """

            chunks = self.chunk_text(full_text)

            if not chunks:
                continue

            embeddings = await self.create_embeddings_batch(chunks)

            for chunk_idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                try:
                    await self._embed_document_content_with_vector(
                        db=db,
                        doc_type="help",
                        master_id=help_centre.id,
                        section_title=section.title,
                        content=chunk,
                        embedding_vector=embedding,
                        chunk_index=chunk_index,
                        total_chunks=len(chunks),
                        metadata={
                            "section_id": section.id,
                            "section_order": section.order,
                            "local_chunk_index": chunk_idx,
                            "content_type": "help",
                            "version": f"v{help_centre.id}",
                            "effective_from": (
                                help_centre.effective_from.isoformat()
                                if help_centre.effective_from
                                else None
                            ),
                            "is_active": help_centre.is_active,
                            "tags": [
                                "help",
                                "support",
                                "guide",
                                section.title.lower().replace(" ", "_"),
                            ],
                        },
                    )
                    count += 1
                    chunk_index += 1

                except Exception as e:
                    logger.error(
                        f"Error embedding help centre chunk {chunk_idx}: {str(e)}"
                    )
                    continue

        logger.info(f"Embedded {count} chunks from Help Centre v{help_centre.id}")
        return count


    async def _embed_privacy_policy(
        self, db: AsyncSession, privacy: content_models.PrivacyPolicyMaster
    ) -> int:
        """
        Embeds the privacy policy document by processing its sections and contents.
        
        Args:
            db: Database session
            privacy: PrivacyPolicyMaster object containing sections and contents
        
        Returns:
            Number of chunks embedded
        """
        count = 0
        chunk_index = 0

        for section in privacy.sections:
            section_parts = []

            for content in section.contents:
                text = self._extract_text_from_content(content)
                if text and text.strip():
                    # Add content type context
                    if content.type == "text":
                        section_parts.append(f"Policy: {text}")
                    elif content.type == "qa":
                        section_parts.append(f"Privacy Q&A: {text}")
                    elif content.type == "table":
                        section_parts.append(f"Data Table: {text}")

            if not section_parts:
                continue

            full_text = f"""
            Privacy Policy
            Section: {section.title}
            {chr(10).join(section_parts)}
            """

            chunks = self.chunk_text(full_text)

            if not chunks:
                continue

            embeddings = await self.create_embeddings_batch(chunks)

            for chunk_idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                try:
                    await self._embed_document_content_with_vector(
                        db=db,
                        doc_type="privacy",
                        master_id=privacy.id,
                        section_title=section.title,
                        content=chunk,
                        embedding_vector=embedding,
                        chunk_index=chunk_index,
                        total_chunks=len(chunks),
                        metadata={
                            "section_id": section.id,
                            "section_order": section.order,
                            "local_chunk_index": chunk_idx,
                            "content_type": "privacy",
                            "version": f"v{privacy.id}",
                            "effective_from": (
                                privacy.effective_from.isoformat()
                                if privacy.effective_from
                                else None
                            ),
                            "is_active": privacy.is_active,
                            "tags": ["privacy", "policy", "legal", "data_protection"],
                        },
                    )
                    count += 1
                    chunk_index += 1

                except Exception as e:
                    logger.error(
                        f"Error embedding privacy policy chunk {chunk_idx}: {str(e)}"
                    )
                    continue

        logger.info(f"Embedded {count} chunks from Privacy Policy v{privacy.id}")
        return count


    async def embed_all_documents(
        self, db: AsyncSession
    ) -> embedding_schemas.DocumentBatchResult:
        """
        Embeds all active documents including terms, FAQ, help centre, and privacy policy.
        
        Args:
            db: Database session
        
        Returns:
            DocumentBatchResult containing processing statistics
        """
        # Import here to avoid circular dependency
        from .content_services import content_service
        
        try:
            stats = {
                "total_processed": 0,
                "terms": 0,
                "faq": 0,
                "help": 0,
                "privacy": 0,
                "errors": 0,
            }

            start_time = datetime.now(timezone.utc)

            await db.execute(delete(DocumentEmbedding))
            logger.info("Cleared existing document embeddings")

            document_pipeline = [
                {
                    "name": "Terms & Conditions",
                    "type": "terms",
                    "fetch_func": content_service.get_active_terms,
                    "embed_func": self._embed_terms,
                },
                {
                    "name": "FAQ",
                    "type": "faq",
                    "fetch_func": content_service.get_active_faq,
                    "embed_func": self._embed_faq,
                },
                {
                    "name": "Help Centre",
                    "type": "help",
                    "fetch_func": content_service.get_active_help_centre,
                    "embed_func": self._embed_help_centre,
                },
                {
                    "name": "Privacy Policy",
                    "type": "privacy",
                    "fetch_func": content_service.get_active_privacy_policy,
                    "embed_func": self._embed_privacy_policy,
                },
            ]

            for doc_config in document_pipeline:
                doc_name = doc_config["name"]
                doc_type = doc_config["type"]

                try:
                    document = await doc_config["fetch_func"](db)

                    if not document:
                        logger.warning(f"No active {doc_name} found")
                        continue

                    count = await doc_config["embed_func"](db, document)
                    stats[doc_type] = count
                    stats["total_processed"] += count

                except Exception as e:
                    logger.error(
                        f"Error processing {doc_name}: {str(e)}", exc_info=True
                    )
                    stats["errors"] += 1

            await db.commit()
            end_time = datetime.now(timezone.utc)
            duration_seconds = (end_time - start_time).total_seconds()
            logger.info(f"Document embedding completed in {duration_seconds} seconds")
            return embedding_schemas.DocumentBatchResult.model_validate(stats)

        except Exception as e:
            await db.rollback()
            logger.error(
                f"Fatal error in document embedding batch: {str(e)}", exc_info=True
            )
            raise


embedding_service = EmbeddingService()
