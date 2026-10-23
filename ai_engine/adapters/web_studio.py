"""Web Studio channel adapter.

Normalizes payloads originating from the internal Web Studio editing environment.
"""

from typing import Any, Dict, Optional
import uuid
from ai_engine.adapters.base import BaseChannelAdapter
from ai_engine.schemas.payload import (
    ChannelType,
    DraftPayload,
    ImageItem,
    VisualMetadata,
)


class WebStudioAdapter(BaseChannelAdapter):
    """Adapter for Web Studio drafting interface."""

    def normalize(
        self,
        raw_input: Any,
        brand_id: str,
        draft_id: Optional[str] = None,
    ) -> DraftPayload:
        if raw_input is None:
            raise ValueError("Web Studio payload cannot be None")

        if isinstance(raw_input, DraftPayload):
            # Already normalized, enforce trusted brand_id
            return raw_input.model_copy(update={"brand_id": brand_id})

        if isinstance(raw_input, dict):
            resolved_draft_id = draft_id or raw_input.get("draft_id") or str(uuid.uuid4())
            content_text = raw_input.get("content_text") or raw_input.get("text") or ""
            supplied_evidence = raw_input.get("supplied_evidence")

            # Parse visual metadata if provided
            vm_raw = raw_input.get("visual_metadata")
            visual_metadata = None
            if isinstance(vm_raw, dict):
                visual_metadata = VisualMetadata(**vm_raw)
            elif isinstance(vm_raw, VisualMetadata):
                visual_metadata = vm_raw

            # Parse images if provided
            images = []
            for img in raw_input.get("images", []):
                if isinstance(img, ImageItem):
                    images.append(img)
                elif isinstance(img, dict):
                    images.append(ImageItem(**img))

            metadata = raw_input.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}

            return DraftPayload(
                draft_id=resolved_draft_id,
                brand_id=brand_id,
                channel=ChannelType.WEB_STUDIO,
                content_text=str(content_text),
                images=images,
                visual_metadata=visual_metadata,
                supplied_evidence=supplied_evidence,
                metadata=metadata,
            )

        # Handle object with attributes
        resolved_draft_id = draft_id or getattr(raw_input, "draft_id", None) or str(uuid.uuid4())
        content_text = getattr(raw_input, "content_text", getattr(raw_input, "text", ""))
        supplied_evidence = getattr(raw_input, "supplied_evidence", None)
        visual_metadata = getattr(raw_input, "visual_metadata", None)

        return DraftPayload(
            draft_id=resolved_draft_id,
            brand_id=brand_id,
            channel=ChannelType.WEB_STUDIO,
            content_text=str(content_text),
            visual_metadata=visual_metadata,
            supplied_evidence=supplied_evidence,
            metadata={},
        )
