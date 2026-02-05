from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from motor.motor_asyncio import AsyncIOMotorDatabase
from azure.storage.blob.aio import ContainerClient, BlobServiceClient


from app.database import session_sql, session_mongo, blob_storage


async def get_postgres_checkpointer():
    """
    PostgreSQL checkpointer dependency.

    Args:
        None

    Returns:
        The PostgreSQL checkpointer instance.
    """
    if session_sql._checkpointer is None:
        raise Exception("PostgreSQL checkpointer is not initialized.")
    return session_sql._checkpointer


async def get_sql_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an async SQLAlchemy session.
    
    Args:
        None

    Yields:
        An instance of AsyncSession.
    """
    async with session_sql.AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_mongo_db() -> AsyncIOMotorDatabase:
    """
    Provide the MongoDB database instance.
    
    Args:
        None

    Returns:
        An instance of AsyncIOMotorDatabase.
    """
    if session_mongo.mongo_manager.db is None:
        raise Exception("MongoDB connection is not initialized.")
    return session_mongo.mongo_manager.db


def get_blob_service_client() -> BlobServiceClient:
    """
    Provide the Azure Blob Service client.

    Args:
        None

    Returns:
        An instance of BlobServiceClient.
    """
    return blob_storage.get_blob_service_client()


async def get_container_client(container: str) -> ContainerClient:
    """
    Provide an Azure Blob Storage container client.

    Args:
        container (str): The name of the container.

    Yields:
        An instance of ContainerClient.
    """
    return blob_storage.get_blob_service_client().get_container_client(container)