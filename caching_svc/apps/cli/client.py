from dataclasses import dataclass
from uuid import UUID

import httpx

from caching_svc.apps.website.schemas import (
    PayloadCreatedSchema,
    PayloadCreateSchema,
    PayloadSchema,
)


@dataclass
class PayloadClient:
    """Thin typed wrapper over the caching service HTTP API."""

    http: httpx.Client

    def create(self, payload: PayloadCreateSchema) -> tuple[PayloadCreatedSchema, bool]:
        """Return the payload id and whether the service generated a new payload."""
        response = self.http.post("/payload", json=payload.model_dump())
        response.raise_for_status()
        created = response.status_code == httpx.codes.CREATED
        return PayloadCreatedSchema.model_validate_json(response.content), created

    def get(self, payload_id: UUID) -> PayloadSchema:
        response = self.http.get(f"/payload/{payload_id}")
        response.raise_for_status()
        return PayloadSchema.model_validate_json(response.content)
