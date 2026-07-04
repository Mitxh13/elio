"""
Groq provider — runs Llama 3, Mixtral, Gemma via Groq's ultra-fast inference.
100% FREE tier available. No billing issues.
API key: console.groq.com (free sign-up, takes 30 seconds)
"""

from typing import AsyncIterator
from openai import AsyncOpenAI   # Groq is OpenAI-API-compatible

from elio.providers.base import BaseProvider, Message, FileAttachment, ModelInfo
from elio.auth.manager import get_api_key


class GroqProvider(BaseProvider):

    def __init__(self):
        key = get_api_key("groq")
        if not key:
            raise RuntimeError(
                "No Groq API key. Run `elio login` and add your free Groq key "
                "from console.groq.com"
            )
        # Groq uses the OpenAI-compatible API — just a different base_url
        self.client = AsyncOpenAI(
            api_key=key,
            base_url="https://api.groq.com/openai/v1",
        )

    def validate_credentials(self) -> bool:
        return get_api_key("groq") is not None

    async def list_models(self) -> list[ModelInfo]:
            return [
                # Valid Groq models
                ModelInfo("llama-3.3-70b", "llama-3.3-70b-versatile", "groq", "Best free model — fast & smart"),
                ModelInfo("llama-3.1-8b", "llama-3.1-8b-instant", "groq", "Ultra-fast, lightweight"),
            ]

    async def stream_chat(
        self,
        messages: list[Message],
        model: str = "llama-3.3-70b-versatile",
        files: list[FileAttachment] | None = None,
        alias: str | None = None,
    ) -> AsyncIterator[str]:
        api_messages = []

        for i, msg in enumerate(messages):
            if i < len(messages) - 1 or msg.role == "assistant":
                api_messages.append({"role": msg.role, "content": msg.content})
            else:
                # Last user message — Groq doesn't support image/file attachments
                # so inject text files as plain text
                content_parts = []
                if files:
                    for f in files:
                        if f.mime_type == "text/plain" or f.mime_type.startswith("text/"):
                            text = f.data.decode("utf-8", errors="replace")
                            content_parts.append(f"[File: {f.name}]\n```\n{text}\n```\n\n")
                        else:
                            content_parts.append(f"[Note: {f.name} ({f.mime_type}) attached but Groq only supports text files]\n\n")
                content_parts.append(msg.content)
                api_messages.append({"role": "user", "content": "".join(content_parts)})

        stream = await self.client.chat.completions.create(
            model=model,
            messages=api_messages,
            max_tokens=4096,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
