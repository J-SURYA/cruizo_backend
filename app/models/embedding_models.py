from sqlalchemy import Column, Integer, DateTime, String, Text, Index, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector


from .base import Base


class CarEmbedding(Base):
    """
    Vector embeddings for car descriptions and features.
    """

    __tablename__ = "car_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    car_id = Column(
        Integer, ForeignKey("cars.id"), nullable=False, unique=True, index=True
    )

    content = Column(Text, nullable=False)
    embedding = Column(Vector(384), nullable=False)
    meta_data = Column(JSONB, nullable=True)

    search_count = Column(Integer, default=0, nullable=False)
    last_searched_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    car = relationship("Car", backref="embedding", lazy="selectin")

    __table_args__ = (
        Index(
            "idx_car_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class DocumentEmbedding(Base):
    """
    Vector embeddings for various documents like terms, FAQ, help, privacy policy.
    """

    __tablename__ = "document_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_type = Column(String(50), nullable=False, index=True)
    doc_id = Column(String(255), nullable=True, index=True)
    title = Column(String(500), nullable=True)

    chunk_index = Column(Integer, nullable=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(384), nullable=False)
    meta_data = Column(JSONB, nullable=True)

    search_count = Column(Integer, default=0, nullable=False)
    last_searched_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "idx_document_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("idx_document_type_id", "doc_type", "doc_id"),
        Index("idx_doc_type_title", "doc_type", "title"),
        Index("idx_doc_chunks", "doc_id", "chunk_index"),
        Index("idx_metadata_gin", "meta_data", postgresql_using="gin"),
    )
