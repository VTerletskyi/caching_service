from fastapi import Depends

from caching_svc.config import settings
from caching_svc.database import session_factory
from caching_svc.shared.application.services import PayloadService
from caching_svc.shared.clients.transformer import Transformer, UppercaseTransformer


_transformer = UppercaseTransformer(delay_seconds=settings.transformer.delay_seconds)


def get_transformer() -> Transformer:
    return _transformer


def get_payload_service(transformer: Transformer = Depends(get_transformer)) -> PayloadService:
    return PayloadService(
        session_factory=session_factory,
        transformer=transformer,
        max_concurrency=settings.transformer.max_concurrency,
    )
