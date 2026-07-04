"""
Elio CLI — Main entry point.
"""

import typer
import sys
from typing import Optional
from rich.console import Console

app = typer.Typer(
    name="elio",
    help="Unified AI CLI — Claude, Gemini, ChatGPT, Groq in one terminal.",
    add_completion=False,
    no_args_is_help=False,
)

console = Console()

VERSION = "0.3.0"


def version_callback(value: bool):
    if value:
        console.print(f"[bold #d4a574]Elio[/bold #d4a574] version [bold]{VERSION}[/bold]")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p",
        help="Set AI provider (google, anthropic, openai, groq).",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Set model alias directly (skips selector).",
    ),
):
    """
    Elio — Unified AI CLI.

    Run without a subcommand to open the interactive chat with model selector.
    """
    if ctx.invoked_subcommand is None:
        from cli.chat import run_chat
        run_chat(provider_override=provider, model_override=model)


# ── Subcommands ──────────────────────────────────────────────────────────────

@app.command()
def login(
    provider: Optional[str] = typer.Argument(None, help="Provider: groq, anthropic, google, openai"),
):
    """Add or update API keys for AI providers."""
    from cli.commands import run_login
    run_login(provider)


@app.command()
def logout():
    """Remove all stored credentials."""
    from cli.commands import run_logout
    run_logout()


@app.command()
def status():
    """Check which AI providers are connected."""
    from cli.commands import run_status
    run_status()


@app.command()
def models():
    """List all available models across all providers."""
    from cli.commands import run_models
    run_models()


@app.command()
def history():
    """Browse saved conversation sessions."""
    from cli.commands import run_history
    run_history()


@app.command()
def config():
    """Open the Elio config file in your default editor."""
    from cli.commands import run_config
    run_config()


@app.command()
def update():
    """Update Elio to the latest version (via pip — no file downloads)."""
    from cli.commands import run_update
    run_update()


if __name__ == "__main__":
    app()
