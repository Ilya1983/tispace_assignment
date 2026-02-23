"""Create database tables. Run once on container startup."""

from sqlalchemy import create_engine

from app.config import settings
from app.database import Base
from app.models import Article  # noqa: F401 — registers model with Base

engine = create_engine(settings.database_url_sync)
Base.metadata.create_all(engine)
engine.dispose()
print("Database tables created successfully.")
