"""What the vision model tells us about an image."""

from typing import List, Optional

from pydantic import BaseModel, Field


class LogoSighting(BaseModel):
    name: str
    # Pixel box (x1, y1, x2, y2) in the image that was shown to the model, if it gave one.
    box: Optional[List[float]] = None


class ImageUnderstanding(BaseModel):
    description: str = ""
    logos: List[LogoSighting] = Field(default_factory=list)
    alt_text_matches: Optional[bool] = None
    alt_text_reason: str = ""
