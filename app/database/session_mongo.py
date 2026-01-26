from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


from app.core.config import settings


class MongoManager:
    """
    Manages the asynchronous MongoDB connection and database instance.
    """

    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


mongo_manager = MongoManager()


async def connect_to_mongo():
    """
    Establishes the MongoDB client connection and set the database instance.

    Args:
        None

    Returns:
        None
    """
    mongo_manager.client = AsyncIOMotorClient(settings.MONGO_URI)
    mongo_manager.db = mongo_manager.client[settings.MONGO_DB]

    try:
        await mongo_manager.client.admin.command("ping")
    except Exception as e:
        raise Exception(f"Failed to connect to MongoDB: {e}")


async def close_mongo_connection():
    """
    Closes the MongoDB client connection.
    
    Args:
        None

    Returns:
        None
    """
    if mongo_manager.client:
        mongo_manager.client.close()
