from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def generate_prefixed_id(db: AsyncSession, prefix: str) -> str:
    """
    Generate a unique sequential ID with a prefix using PostgreSQL sequences.
    
    Example:
        prefix="U" → "U0001", "U0002", ...

    Args:
        db (AsyncSession): Active DB session.
        prefix (str): ID prefix (e.g., "U" for user).

    Returns:
        str: Prefixed unique ID.
    """
    sequence_name = f"{prefix.lower()}_id_seq"
    result = await db.execute(text(f"SELECT nextval('{sequence_name}')"))
    next_val = result.scalar()
    return f"{prefix.upper()}{next_val:04d}"
