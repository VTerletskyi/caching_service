from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from caching_svc.config import settings


engine = create_async_engine(
    settings.database.url,
    echo=settings.database.echo,
    **({"poolclass": NullPool} if settings.database.use_null_pool else {}),
)
session_factory = async_sessionmaker(engine, expire_on_commit=False)
