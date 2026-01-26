from sqlalchemy import Column, DateTime, Integer, String, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship


from .base import Base


class ChatSession(Base):
    """
    User chat session model.
    """

    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    title = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    threads = relationship(
        "ChatThread", back_populates="session", cascade="all, delete-orphan"
    )
    user = relationship("User", foreign_keys=[user_id], lazy="noload")


class ChatThread(Base):
    """
    User chat thread model.
    """

    __tablename__ = "chat_threads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(String, unique=True, nullable=False, index=True)
    session_id = Column(
        Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True
    )

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    session = relationship("ChatSession", back_populates="threads")
