import httpx
from typing import Optional, Dict


from app.core.config import settings
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


async def reverse_geocode(latitude: float, longitude: float) -> Optional[str]:
    """
    Convert latitude & longitude into a human-readable address.

    Args:
        latitude (float): Latitude value.
        longitude (float): Longitude value.

    Returns:
        Optional[str]: Formatted address if found, else None.
    """
    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "latlng": f"{latitude},{longitude}",
            "key": settings.GOOGLE_GEOCODING_API_KEY,
        }

        if not settings.GOOGLE_GEOCODING_API_KEY:
            logger.error("Google Geocoding API key is not configured")
            return None

        logger.info(
            f"Calling Google Geocoding API for coordinates {latitude}, {longitude}"
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()

        status = data.get("status")
        logger.info(f"Google Geocoding API status: {status}")

        if status == "OK" and data.get("results"):
            address = data["results"][0].get("formatted_address")
            logger.info(f"Resolved address: {address}")
            return address

        if status == "ZERO_RESULTS":
            logger.warning(f"No results found for {latitude}, {longitude}")
        elif status == "REQUEST_DENIED":
            logger.error(f"Geocoding request denied: {data.get('error_message')}")
        elif status == "OVER_QUERY_LIMIT":
            logger.error("Geocoding API quota exceeded")
        else:
            logger.warning(
                f"Reverse geocoding failed: {status} - {data.get('error_message', 'Unknown error')}"
            )

        return None

    except httpx.HTTPStatusError as e:
        logger.error(
            f"HTTP error during reverse geocoding: {e.response.status_code} {e.response.text}"
        )
        return None
    except Exception as e:
        logger.error(f"Unexpected error in reverse geocoding: {e}", exc_info=True)
        return None


async def geocode(address: str) -> Optional[Dict[str, float]]:
    """
    Convert a physical address into latitude & longitude.

    Args:
        address (str): Full address to resolve.

    Returns:
        Optional[Dict[str, float]]: Latitude & longitude dict, else None.
    """
    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {"address": address, "key": settings.GOOGLE_GEOCODING_API_KEY}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()

        if data.get("status") == "OK" and data.get("results"):
            location = data["results"][0]["geometry"]["location"]
            return {
                "latitude": location.get("lat"),
                "longitude": location.get("lng"),
            }

        logger.warning(
            f"Geocoding failed: {data.get('status')} - {data.get('error_message', 'Unknown error')}"
        )
        return None

    except Exception as e:
        logger.error(f"Unexpected error in geocoding: {e}")
        return None
