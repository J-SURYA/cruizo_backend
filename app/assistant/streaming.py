import json
from typing import AsyncGenerator, Dict, Any
from fastapi.responses import StreamingResponse


from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


async def create_sse_stream(
    generator: AsyncGenerator[Dict[str, Any], None],
) -> StreamingResponse:
    """
    Create Server-Sent Events stream from async generator.
    
    Args:
        generator (AsyncGenerator[Dict[str, Any], None]): An async generator yielding event dictionaries.
    
    Returns:
        StreamingResponse: A FastAPI StreamingResponse configured for SSE.
    """
    async def event_generator():
        try:
            async for event in generator:
                try:
                    event_type = event.get("type")

                    if event_type == "token":
                        yield f"data: {json.dumps({
                            'type': 'token',
                            'node': event.get('node'),
                            'token': event.get('token', ''),
                            'complete': False
                        })}\n\n"

                    elif event_type == "node_start":
                        yield f"data: {json.dumps({
                            'type': 'node_start',
                            'node': event.get('node'),
                            'complete': False
                        })}\n\n"

                    elif event_type == "node_complete":
                        yield f"data: {json.dumps({
                            'type': 'node_complete',
                            'node': event.get('node'),
                            'intent': event.get('intent'),
                            'sub_intent': event.get('sub_intent'),
                            'confidence_score': event.get('confidence'),
                            'status': event.get('status'),
                            'complete': False
                        })}\n\n"

                    elif event_type == "error":
                        yield f"data: {json.dumps({
                            'type': 'error',
                            'error': event.get('error', 'Unknown error'),
                            'complete': True
                        })}\n\n"

                    elif event_type == "complete":
                        yield f"data: {json.dumps({
                            'type': 'complete',
                            'response': event.get('response', {}),
                            'complete': True
                        })}\n\n"

                except (TypeError, ValueError) as e:
                    logger.error(f"JSON serialization error: {e}")
                    yield f"data: {json.dumps({
                        'type': 'error',
                        'error': 'Serialization failed',
                        'complete': True
                    })}\n\n"

        except Exception as e:
            logger.error(f"SSE stream error: {str(e)}")
            yield f"data: {json.dumps({
                'type': 'error',
                'error': str(e),
                'complete': True
            })}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["create_sse_stream"]
