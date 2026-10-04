import logging

import uvicorn

from fastapi import FastAPI

from caching_svc.apps.website.routes.payload import router as payload_router
from caching_svc.config import settings


def create_website_app() -> FastAPI:
    """Create FastAPI website application for caching service."""
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app_settings = settings.applications.website
    app = FastAPI(
        title=app_settings.title,
        description=app_settings.description,
        version=app_settings.version,
        docs_url=app_settings.docs_url,
    )
    app.include_router(payload_router)
    return app


app = create_website_app()


def run():
    """Run the FastAPI application"""
    uvicorn.run(
        "caching_svc.apps.website.app:app",
        host=settings.applications.website.host,
        port=settings.applications.website.port,
        reload=settings.applications.website.reload,
    )


if __name__ == "__main__":
    run()
