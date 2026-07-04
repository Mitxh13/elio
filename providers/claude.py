import base64
import asyncio
from typing import AsyncIterator
import anthropic

from elio.providers.base import BaseProvider, Message, FileAttachment, ModelInfo
from elio.auth.manager import get_api_key


class ClaudeProvider(BaseProvider):

    def __init__(self):
        key = get_api_key("anthropic")
        if not key:
            raise RuntimeError(
                "No Anthropic API key found. Run `elio login anthropic`."
            )
        # Async client — all calls are awaited inside stream_chat
        self.client = anthropic.AsyncAnthropic(api_key=key)

    def validate_credentials(self) -> bool:
        return get_api_key("anthropic") is not None

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo("claude-sonnet", "claude-sonnet-5",           "anthropic", "Best for coding & reasoning"),
            ModelInfo("claude-opus",   "claude-opus-4-8",           "anthropic", "Most capable — complex agentic tasks"),
            ModelInfo("claude-haiku",  "claude-haiku-4-5-20251001", "anthropic", "Fast & affordable"),
        ]

    async def stream_chat(
        self,
        messages: list[Message],
        model: str = "claude-sonnet-5",
        files: list[FileAttachment] | None = None,
        alias: str | None = None,
    ) -> AsyncIterator[str]:
        # Build the content list for the last user message
        # (previous messages in the list are just role/text pairs)
        api_messages = []

        for i, msg in enumerate(messages):
            if i < len(messages) - 1 or msg.role == "assistant":
                # Historical messages — plain text only
                api_messages.append({"role": msg.role, "content": msg.content})
            else:
                # Last user message — may have file attachments
                content = []

                # Add file blocks before the text
                if files:
                    for f in files:
                        if f.mime_type.startswith("image/"):
                            content.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": f.mime_type,
                                    "data": base64.b64encode(f.data).decode(),
                                },
                            })
                        elif f.mime_type == "application/pdf":
                            content.append({
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": base64.b64encode(f.data).decode(),
                                },
                            })
                        else:
                            # Text file — inject as a code block
                            text_content = f.data.decode("utf-8", errors="replace")
                            content.append({
                                "type": "text",
                                "text": f"```{f.name}\n{text_content}\n```",
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
                # Open a streaming context and yield each token as it arrives
                async with self.client.messages.stream(
                    model=model,
                    max_tokens=4096,
                    messages=api_messages,
                ) as stream:
                    async for text in stream.text_stream:
                        yield text
                return   # success — done

            except anthropic.RateLimitError:
                continue   # will retry after sleep

            except anthropic.AuthenticationError:
                yield (
                    "\n[red]Claude authentication failed.[/red]\n"
                    "[dim]  Run [bold cyan]elio login anthropic[/bold cyan] to update your API key.[/dim]\n"
                )
                return

            except anthropic.NotFoundError as e:
                yield (
                    f"\n[red]Claude model not found:[/red] '{model}'\n"
                    f"[dim]  Run [bold cyan]/models[/bold cyan] to see available models.[/dim]\n"
                )
                return

            except anthropic.BadRequestError as e:
                err_str = str(e).lower()
                if "credit" in err_str or "billing" in err_str or "insufficient" in err_str:
                    yield (
                        "\n[yellow]No credits remaining on this Anthropic account.[/yellow]\n"
                        "[dim]  💡 Switch to a FREE model: /provider → Groq or Google[/dim]\n"
                    )
                else:
                    yield f"\n[red]Claude error:[/red] {e}\n"
                return

            except Exception as e:
                err_str = str(e).lower()
                if "429" in str(e) or "rate" in err_str:
                    continue
                yield f"\n[red]Claude error:[/red] {e}\n"
                return

        # All 3 retries exhausted
        yield (
            "\n[red]Rate limit reached after 3 attempts.[/red]\n"
            "[dim]  • Wait a minute and try again\n"
            "  • Switch to a different provider with /provider[/dim]\n"
        )