from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Article
from app.schemas import ArticleDetail, ArticleListItem, PaginatedResponse

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=PaginatedResponse)
async def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search_keyword: str | None = None,
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Article)
    count_query = select(func.count()).select_from(Article)

    if search_keyword:
        query = query.where(Article.search_keyword == search_keyword)
        count_query = count_query.where(Article.search_keyword == search_keyword)
    if source:
        query = query.where(Article.source == source)
        count_query = count_query.where(Article.source == source)

    total = (await db.execute(count_query)).scalar()

    query = query.order_by(Article.published_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        results=[ArticleListItem.model_validate(r) for r in rows],
    )


@router.get("/{article_id}", response_model=ArticleDetail)
async def get_article(article_id: UUID, db: AsyncSession = Depends(get_db)):
    article = (
        await db.execute(select(Article).where(Article.id == article_id))
    ).scalar_one_or_none()

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    return ArticleDetail.model_validate(article)


@router.get("/{article_id}/summary")
async def get_summary(article_id: UUID, db: AsyncSession = Depends(get_db)):
    article = (
        await db.execute(select(Article).where(Article.id == article_id))
    ).scalar_one_or_none()

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    raise HTTPException(status_code=501, detail="Summary endpoint not yet implemented")
