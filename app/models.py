import uuid

from sqlalchemy import Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Article(Base):
    __tablename__ = "articles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_uuid = Column(String, unique=True, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text)
    snippet = Column(Text)
    content = Column(Text, nullable=True)
    url = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    source = Column(String)
    language = Column(String, default="en")
    published_at = Column(DateTime(timezone=True))
    search_keyword = Column(String)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
