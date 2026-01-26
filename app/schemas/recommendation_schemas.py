from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime


class RecommendationResponse(BaseModel):
    """
    Schema for recommendations.
    """
    recommendations: List[Dict[str, Any]]
    based_on: List[str]
    generated_at: datetime
    expires_at: datetime
    confidence_score: Optional[float] = None
