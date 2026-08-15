import mimetypes
from pathlib import Path
from providers.base import FileAttachment

# File types Elio can handle
SUPPORTED_EXTENSIONS = {
    # Images
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif":  "image/gif",
    ".webp": "image/webp",
    # Documents
    ".pdf":  "application/pdf",
    # Text / code
    ".txt":  "text/plain",
    ".md":   "text/plain",
    ".py":   "text/plain",
    ".js":   "text/plain",
    ".ts":   "text/plain",
    ".csv":  "text/plain",
    ".json": "text/plain",
    ".yaml": "text/plain",
    ".toml": "text/plain",
    ".html": "text/plain",
    ".css":  "text/plain",
    ".sql":  "text/plain",
}

# Provider support matrix — not all providers handle all types
PROVIDER_SUPPORT = {
    "anthropic": {"image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf", "text/plain"},
    "openai":    {"image/png", "image/jpeg", "image/gif", "image/webp", "text/plain"},
    "google":    {"image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf", "text/plain"},
    "groq":      {"text/plain"},
}


def load_file(path: str) -> FileAttachment:
    """
    Read a file from disk and return a FileAttachment ready for any provider adapter.
    Raises ValueError if the file type is unsupported.
    """
    p = Path(path).expanduser().resolve()

    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    ext = p.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(SUPPORTED_EXTENSIONS.keys())
        raise ValueError(f"Unsupported file type '{ext}'. Supported: {supported}")

    mime = SUPPORTED_EXTENSIONS[ext]
    data = p.read_bytes()

    return FileAttachment(name=p.name, mime_type=mime, data=data)


def check_provider_support(attachment: FileAttachment, provider: str) -> bool:
    """Return True if the provider supports this file type."""
    supported = PROVIDER_SUPPORT.get(provider, set())
    return attachment.mime_type in supported