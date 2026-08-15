"""
Google Gemini provider.
Supports both API key and Google OAuth ("Sign in with Google") auth.
"""

import asyncio
from typing import AsyncIterator
from google import genai
from google.genai import types

from providers.base import BaseProvider, Message, FileAttachment, ModelInfo
from auth.manager import get_api_key


# ── Model strings ─────────────────────────────────────────────────────────────
# Keep these in sync with providers/registry.py

GEMINI_FAST      = "gemini-2.5-flash"         # free tier, fast responses
GEMINI_PRO       = "gemini-2.5-pro"           # most capable, default thinking
GEMINI_THINKING  = "gemini-2.5-pro"           # same model, explicit thinking budget


class GeminiProvider(BaseProvider):

    def __init__(self):
        from auth.oauth import get_google_credentials
        creds = get_google_credentials()
        if creds:
            self.client = genai.Client(credentials=creds)
            return

        key = get_api_key("google")
        if key:
            self.client = genai.Client(api_key=key)
            return

        raise RuntimeError(
            "No Google credentials.\n"
            "  Option 1: Run `elio login` → choose Google → Sign in with Google\n"
            "  Option 2: Run `elio login` → choose Google → Enter API key (free at aistudio.google.com)"
        )

    def validate_credentials(self) -> bool:
        from auth.oauth import is_google_oauth_logged_in
        return get_api_key("google") is not None or is_google_oauth_logged_in()

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                "gemini-fast",
                GEMINI_FAST,
                "google",
                "Fast & free — great for quick questions and research",
            ),
            ModelInfo(
                "gemini-pro",
                GEMINI_PRO,
                "google",
                "Most capable — complex reasoning, math, and long docs",
            ),
            ModelInfo(
                "gemini-thinking",
                GEMINI_THINKING,
                "google",
                "Extended thinking mode — slower but deeper reasoning",
            ),
        ]

    async def stream_chat(
        self,
        messages: list[Message],
        model: str = GEMINI_FAST,
        files: list[FileAttachment] | None = None,
        alias: str | None = None,
    ) -> AsyncIterator[str]:

        # ── 1. Build conversation history ─────────────────────────────────────
        contents = []
        for msg in messages[:-1]:
            role = "user" if msg.role == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg.content)],
                )
            )

        # ── 2. Build the final user turn (with optional file attachments) ─────
        parts: list = []
        if files:
            for f in files:
                try:
                    if f.mime_type.startswith("image/"):
                        parts.append(
                            types.Part.from_bytes(data=f.data, mime_type=f.mime_type)
                        )
                    elif f.mime_type == "application/pdf":
                        # Gemini 2.5 Pro supports native PDF understanding
                        parts.append(
                            types.Part.from_bytes(data=f.data, mime_type="application/pdf")
                        )
                    else:
                        # Text / code / CSV / JSON → inject as a fenced block
                        text_content = f.data.decode("utf-8", errors="replace")
                        parts.append(
                            types.Part.from_text(
                                text=f"### Attached file: {f.name}\n```\n{text_content}\n```"
                            )
                        )
                except Exception as file_err:
                    parts.append(
                        types.Part.from_text(
                            text=f"[Could not attach {getattr(f, 'name', 'file')}: {file_err}]"
                        )
                    )

        parts.append(types.Part.from_text(text=messages[-1].content))
        contents.append(types.Content(role="user", parts=parts))

        # ── 3. Thinking config — only for models that support it ──────────────
        #
        #  gemini-fast      (gemini-2.5-flash)  → NO explicit thinking, let model decide
        #  gemini-pro       (gemini-2.5-pro)     → default thinking (model decides)
        #  gemini-thinking  (gemini-2.5-pro)     → explicit high budget for deep reasoning
        #
        generate_config: types.GenerateContentConfig | None = None

        if alias == "gemini-thinking":
            generate_config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=8192),
            )
        # gemini-fast uses gemini-2.5-flash which handles thinking internally —
        # passing an explicit config may cause issues, so we leave generate_config as None.

        stream_kwargs: dict = {"model": model, "contents": contents}
        if generate_config:
            stream_kwargs["config"] = generate_config

        # ── 4. Stream with retry on rate-limit ───────────────────────────────
        for attempt in range(3):
            if attempt > 0:
                wait = 20 * attempt          # 20 s → 40 s
                yield f"\n⚠️  Rate limit hit — waiting {wait}s before retry {attempt}/2...\n"
                await asyncio.sleep(wait)

            try:
                async for chunk in await self.client.aio.models.generate_content_stream(
                    **stream_kwargs
                ):
                    # .text is None for thinking-only chunks; skip them silently
                    text = getattr(chunk, "text", None)
                    if text:
                        yield text
                return   # success — done

            except Exception as e:
                err_str = str(e)
                err_low = err_str.lower()

                # ── Rate limit ───────────────────────────────────────────────
                if "429" in err_str or "quota" in err_low or "rate" in err_low:
                    continue   # will retry after sleep

                # ── Model not found (wrong model string in registry) ──────────
                if ("not found" in err_low or "does not exist" in err_low
                        or "invalid" in err_low and "model" in err_low):
                    yield (
                        f"\n[red]Gemini model not found:[/red] '{model}'\n"
                        f"[dim]  Check providers/registry.py — the model string for "
                        f"'{alias}' may be outdated.\n"
                        f"  Current correct strings: "
                        f"gemini-2.5-flash · gemini-2.5-pro[/dim]\n"
                    )
                    return

                # ── Auth error ───────────────────────────────────────────────
                if ("401" in err_str or "403" in err_str
                        or "api_key" in err_low or "api key" in err_low
                        or "permission" in err_low or "unauthenticated" in err_low):
                    yield (
                        "\n[red]Gemini authentication failed.[/red]\n"
                        "[dim]  Run [bold cyan]elio login[/bold cyan] to update your Google credentials.[/dim]\n"
                    )
                    return

                # ── Thinking config not supported on this model ───────────────
                if "thinking" in err_low or ("thinking_config" in err_low):
                    # Fall back: retry without thinking config
                    stream_kwargs.pop("config", None)
                    generate_config = None
                    yield "\n[dim]Thinking not supported on this model — retrying without it...[/dim]\n"
                    continue

                # ── Any other error ───────────────────────────────────────────
                yield f"\n[red]Gemini error:[/red] {err_str}\n"
                return

        # All 3 retries exhausted (only reaches here on repeated rate-limit)
        yield (
            "\n[red]Rate limit reached after 3 attempts.[/red]\n"
            "[dim]  • Switch to Gemini Fast (/provider) — higher free-tier quota\n"
            "  • Wait a minute and try again\n"
            "  • Get a free API key at aistudio.google.com for higher limits[/dim]\n"
        )