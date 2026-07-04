from abc import ABC, abstractmethod
from typing import AsyncIterator
from dataclasses import dataclass, field


@dataclass
class Message:
    """A single turn in the conversation."""
    role: str           # "user" | "assistant"
    content: str        # text content of the message


@dataclass
class FileAttachment:
    """A file the user attached with Ctrl+U or /attach."""
    name: str           # original filename
    mime_type: str      # e.g. "image/png", "application/pdf", "text/plain"
    data: bytes         # raw bytes of the file


@dataclass
class ModelInfo:
    """Metadata about a model that elio models can list."""
    alias: str          # e.g. "claude", "coding"
    name: str           # e.g. "claude-sonnet-4-5"
    provider: str       # e.g. "anthropic"
    description: str = ""


class BaseProvider(ABC):
    """
    Every provider adapter (Claude, GPT, Gemini) subclasses this.
    The rest of Elio only talks to this interface — never to provider SDKs directly.
    """

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[Message],
        model: str,
        files: list[FileAttachment] | None = None,
        alias: str | None = None,
    ) -> AsyncIterator[str]:
        """Yield response tokens one by one as they stream from the API."""
        ...

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """Return all models this provider supports."""
        ...

    @abstractmethod
    def validate_credentials(self) -> bool:
        """Return True if the stored API key appears valid (cheap/fast check)."""
        ...