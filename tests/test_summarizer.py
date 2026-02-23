from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.summarizer import summarize_article

pytestmark = pytest.mark.asyncio


@patch("app.services.summarizer.client")
async def test_summarize_article_returns_text(mock_client):
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="This is the summary.")]
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    result = await summarize_article("Some article content here.")

    assert result == "This is the summary."
    mock_client.messages.create.assert_awaited_once()
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
    assert call_kwargs["max_tokens"] == 300
    assert "Some article content here." in call_kwargs["messages"][0]["content"]


@patch("app.services.summarizer.client")
async def test_summarize_article_propagates_error(mock_client):
    mock_client.messages.create = AsyncMock(side_effect=Exception("API down"))

    with pytest.raises(Exception, match="API down"):
        await summarize_article("Content that won't be summarized.")
