from azure.storage.blob.aio import BlobServiceClient
from azure.core.exceptions import ResourceExistsError


from app.core.config import settings


blob_service_client = BlobServiceClient.from_connection_string(
    settings.AZURE_STORAGE_CONNECTION_STRING
)


def get_blob_service_client() -> BlobServiceClient:
    """
    Initializes and returns the Azure Blob Service client.

    Args:
        None

    Returns:
        BlobServiceClient: The Azure Blob Service client.
    """
    return blob_service_client


async def close_blob_service_client():
    """
    Closes the Azure Blob Service client connection.

    Args:
        None

    Returns:
        None
    """
    await blob_service_client.close()


async def verify_containers() -> None:
    """
    Ensure Azure Blob containers exist, creates them if missing.
    
    Args:
        None
    
    Returns:
        None
    """
    for name in [settings.AADHAAR_CONTAINER_NAME, settings.BACKUP_CONTAINER_NAME, settings.BOOKING_CONTAINER_NAME, settings.INVENTORY_CONTAINER_NAME, settings.LICENSE_CONTAINER_NAME, settings.PROFILE_CONTAINER_NAME]:
        container_client = blob_service_client.get_container_client(name)
        try:
            await container_client.create_container()

        except ResourceExistsError:
            continue

        except Exception as exc:
            raise RuntimeError(
                f"Failed to ensure Azure Blob container '{name}'. "
                f"Application startup aborted."
            ) from exc
