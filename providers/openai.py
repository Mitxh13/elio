import base64
import asyncio
from typing import AsyncIterator
from openai import AsyncOpenAI

from elio.providers.base import BaseProvider, Message, FileAttachment, ModelInfo
from elio.auth.manager import get_api_key


class OpenAIProvider(BaseProvider):

    def __init__(self):
        key = get_api_key("openai")
        if not key:
            raise RuntimeError("No OpenAI API key. Run `elio login openai`.")
        self.client = AsyncOpenAI(api_key=key)

    def validate_credentials(self) -> bool:
        return get_api_key("openai") is not None

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo("gpt-4o-mini",  "gpt-4o-mini",  "openai", "Fast & very cheap"),
            ModelInfo("gpt-4o",       "gpt-4o",       "openai", "Multi-modal, writing & creativity"),
            ModelInfo("gpt-4.1",      "gpt-4.1",      "openai", "Latest & most capable"),
            ModelInfo("gpt-4.1-mini", "gpt-4.1-mini", "openai", "Fast latest-gen"),
            ModelInfo("gpt-4.1-nano", "gpt-4.1-nano", "openai", "Ultra-fast, cheapest"),
        ]

    async def stream_chat(
        self,
        messages: list[Message],
        model: str = "gpt-4o-mini",
        files: list[FileAttachment] | None = None,
        alias: str | None = None,
    ) -> AsyncIterator[str]:
        api_messages = []

        for i, msg in enumerate(messages):
            if i < len(messages) - 1 or msg.role == "assistant":
                api_messages.append({"role": msg.role, "content": msg.content})
            else:
                content = []

                if files:
                    for f in files:
                        if f.mime_type.startswith("image/"):
                            b64 = base64.b64encode(f.data).decode()
                            content.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{f.mime_type};base64,{b64}"},
                            })
                        else:
                            text_content = f.data.decode("utf-8", errors="replace")
                            content.append({
                                "type": "text",
                                "text": f"File: {f.name}\n```\n{text_content}\n```",
                            })

                content.append({"type": "text", "text": msg.content})
                api_messages.append({"role": "user", "content": content})

        # ── Stream with retry on rate-limit ───────────────────────────────
        for attempt in range(3):
            if attempt > 0:
                wait = 15 * attempt          # 15 s → 30 s
                yield f"\n⚠️  Rate limit hit — waiting {wait}s before retry {attempt}/2...\n"
                await asyncio.sleep(wait)

            try:
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
                return   # success — done

            except Exception as e:
                err_str = str(e)
                err_low = err_str.lower()

                # ── Rate limit ───────────────────────────────────────────
                if "429" in err_str or "rate" in err_low:
                    continue

                # ── Auth error ───────────────────────────────────────────
                if "401" in err_str or "invalid_api_key" in err_low or "authentication" in err_low:
                    yield (
                        "\n[red]OpenAI authentication failed.[/red]\n"
                        "[dim]  Run [bold cyan]elio login openai[/bold cyan] to update your API key.[/dim]\n"
                    )
                    return

                # ── Billing / quota ──────────────────────────────────────
                if "insufficient_quota" in err_low or "billing" in err_low or "402" in err_str:
                    yield (
                        "\n[yellow]No credits remaining on this OpenAI account.[/yellow]\n"
                        "[dim]  💡 Switch to a FREE model: /provider → Groq or Google[/dim]\n"
                    )
                    return

                # ── Model not found ──────────────────────────────────────
                if "model_not_found" in err_low or "does not exist" in err_low:
                    yield (
                        f"\n[red]OpenAI model not found:[/red] '{model}'\n"
                        f"[dim]  Run [bold cyan]/models[/bold cyan] to see available models.[/dim]\n"
                    )
                    return

                # ── Any other error ──────────────────────────────────────
                yield f"\n[red]OpenAI error:[/red] {err_str}\n"
                return

        # All 3 retries exhausted
        yield (
            "\n[red]Rate limit reached after 3 attempts.[/red]\n"
            "[dim]  • Wait a minute and try again\n"
            "  • Switch to a different provider with /provider[/dim]\n"
        )