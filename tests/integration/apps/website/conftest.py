import pytest

from httpx import ASGITransport, AsyncClient

from caching_svc.apps.website.app import app
from caching_svc.apps.website.deps import get_transformer


@pytest.fixture
async def website_client(transformer):
    app.dependency_overrides[get_transformer] = lambda: transformer
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
