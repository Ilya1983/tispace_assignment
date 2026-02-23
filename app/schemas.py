from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ArticleListItem(BaseModel):
    id: UUID
    external_uuid: str
    title: str
    description: str | None = None
    snippet: str | None = None
    url: str
    image_url: str | None = None
    source: str | None = None
    language: str | None = None
    published_at: datetime | None = None
    search_keyword: str | None = None
    fetched_at: datetime | None = None

    model_config = {"from_attributes": True}


class ArticleDetail(ArticleListItem):
    content: str | None = None


class ArticleSummary(BaseModel):
    id: UUID
    title: str
    summary: str
    cached: bool


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[ArticleListItem]


class FetchResult(BaseModel):
    fetched: int
    skipped: int
    failed: int
