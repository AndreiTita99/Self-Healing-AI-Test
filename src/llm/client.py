import anthropic

from src.config import settings


class LLMClient:
    _MODEL = "claude-haiku-4-5-20251001"

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def complete(self, prompt: str) -> str:
        message = self._client.messages.create(
            model=self._MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
