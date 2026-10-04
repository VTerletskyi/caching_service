from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from caching_svc.apps.website.deps import get_payload_service
from caching_svc.apps.website.schemas import (
    PayloadCreatedSchema,
    PayloadCreateSchema,
    PayloadSchema,
)
from caching_svc.shared.application.services import PayloadService
from caching_svc.shared.domain.exceptions import PayloadNotFoundError, TransformerError


router = APIRouter(
    prefix="/payload",
    tags=["payload"],
)


@router.post(
    "",
    response_model=PayloadCreatedSchema,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {"model": PayloadCreatedSchema},
        status.HTTP_502_BAD_GATEWAY: {"description": "The external transformer service failed"},
    },
)
async def create_payload(
    data: PayloadCreateSchema,
    response: Response,
    service: PayloadService = Depends(get_payload_service),
):
    """Generate a payload, or return the id of the identical payload generated before (200)."""
    try:
        result = await service.create(data.list_1, data.list_2)
    except TransformerError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    if not result.created:
        response.status_code = status.HTTP_200_OK
        return PayloadCreatedSchema(id=result.payload_id, message="Payload already exists")
    return PayloadCreatedSchema(id=result.payload_id, message="Payload created")


@router.get("/{payload_id}", response_model=PayloadSchema)
async def get_payload(
    payload_id: UUID,
    service: PayloadService = Depends(get_payload_service),
):
    """Return the generated payload."""
    try:
        payload = await service.get(payload_id)
    except PayloadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PayloadSchema(output=payload.output)
