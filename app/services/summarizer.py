import anthropic

from app.config import settings

client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def summarize_article(content: str) -> str:
    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": f"Summarize the following news article in 2-3 concise sentences:\n\n{content}",
            }
        ],
    )
    return message.content[0].text
