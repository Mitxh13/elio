"""
Elio CLI — Slash command router.

Handles all /commands typed in the inline chat interface.
Each command returns a CommandResult describing what to display and
what state changes to apply.
"""

from __future__ import annotations
import os
import sys
import platform
import subprocess
import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    os.system("")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from providers.registry import (
    MODEL_REGISTRY, PROVIDERS, PROVIDER_ORDER, PROVIDER_MODELS,
    resolve_model, get_models_for_provider, get_default_model_for_provider,
    ModelEntry,
)
from providers.base import Message
from auth.manager import get_connected_providers, get_api_key
from session.manager import SessionManager
from config.schema import ElioConfig

console = Console()


@dataclass
class CommandResult:
    """Result of a slash command — tells the chat loop what to do."""
    output: str = ""            # text to display
    error: bool = False         # whether this is an error
    new_provider: str | None = None   # switch to this provider
    new_alias: str | None = None      # switch to this model alias
    clear_history: bool = False       # clear conversation context
    should_exit: bool = False         # exit the chat loop


VERSION = "0.3.5"

HELP_TEXT = """
[bold #d4a574]╭─── Elio Commands ───╮[/bold #d4a574]

[bold]Chat & AI[/bold]
  [cyan]/provider[/cyan]           Switch AI provider and model
  [cyan]/model[/cyan] [dim][alias][/dim]    Quick-switch model within current provider
  [cyan]/models[/cyan]             List all models for current provider
  [cyan]/clear[/cyan]              Clear conversation context and screen

[bold]Files & Code[/bold]
  [cyan]/attach[/cyan] [dim]<path>[/dim]     Attach a file to the next message
  [cyan]/read[/cyan] [dim]<path>[/dim]       Read a file and add contents to context
  [cyan]/run[/cyan] [dim]<command>[/dim]     Execute a shell command, capture output

[bold]Sessions[/bold]
  [cyan]/history[/cyan]            List recent saved sessions
  [cyan]/load[/cyan] [dim]<id>[/dim]         Load a previous session by ID
  [cyan]/export[/cyan]             Export current session as markdown
  [cyan]/tokens[/cyan]             Show estimated context token usage

[bold]System[/bold]
  [cyan]/status[/cyan]             Show which providers have API keys
  [cyan]/config[/cyan]             Open config file in your editor
  [cyan]/version[/cyan]            Show Elio version
  [cyan]/help[/cyan]               Show this help text
  [cyan]/exit[/cyan]               Exit Elio

[dim]Shortcuts: Ctrl+C = cancel, Ctrl+D = exit[/dim]
[bold #d4a574]╰──────────────────────╯[/bold #d4a574]
"""


async def route_command(
    cmd: str,
    history: list[Message],
    attached_files: list,
    current_provider: str,
    current_alias: str,
    session_manager: SessionManager,
    config: ElioConfig,
) -> CommandResult:
    """Parse a slash command string and perform the action."""
    parts = cmd.strip().split(maxsplit=1)
    name = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    # ── /help ───────────────────────────────────────────────────────────
    if name == "/help":
        return CommandResult(output=HELP_TEXT)

    # ── /version ────────────────────────────────────────────────────────
    if name == "/version":
        return CommandResult(output=f"[bold #d4a574]Elio[/bold #d4a574] v{VERSION}")

    # ── /exit or /quit ──────────────────────────────────────────────────
    if name in ("/exit", "/quit"):
        return CommandResult(should_exit=True)

    # ── /provider ───────────────────────────────────────────────────────
    if name == "/provider":
        from cli.chat import full_provider_model_select
        result = full_provider_model_select(current_provider, current_alias)
        if result:
            new_provider, new_alias = result
            entry = resolve_model(new_alias)
            info = PROVIDERS[new_provider]
            return CommandResult(
                output=f"\n  [green]>> Switched to {info.name} - {entry.display_name}[/green]\n",
                new_provider=new_provider,
                new_alias=new_alias,
            )
        return CommandResult(output="[dim]  Selection cancelled.[/dim]")

    # ── /model [alias] ──────────────────────────────────────────────────
    if name == "/model":
        if not arg:
            # Show model selector for current provider
            from cli.chat import select_model
            alias = select_model(current_provider, current_alias)
            if alias:
                entry = resolve_model(alias)
                return CommandResult(
                    output=f"\n  [green]>> Switched to {entry.display_name}[/green]\n",
                    new_alias=alias,
                )
            return CommandResult(output="[dim]  Selection cancelled.[/dim]")

        # Direct alias switch
        try:
            entry = resolve_model(arg)
            if entry.provider_name != current_provider:
                return CommandResult(
                    output=(
                        f"[yellow]  '{arg}' belongs to {entry.provider_name}, "
                        f"not {current_provider}. Use /provider to switch.[/yellow]"
                    ),
                    error=True,
                )
            # Check API key
            key = get_api_key(entry.provider_name)
            if not key:
                info = PROVIDERS[entry.provider_name]
                return CommandResult(
                    output=f"[yellow]  ! No API key for {info.name}. Run `elio login {entry.provider_name}`.[/yellow]",
                    error=True,
                )
            return CommandResult(
                output=f"\n  [green]>> Switched to {entry.display_name}[/green]\n",
                new_alias=arg,
            )
        except KeyError as e:
            return CommandResult(output=f"[red]  {e}[/red]", error=True)

    # ── /models ─────────────────────────────────────────────────────────
    if name == "/models":
        models = get_models_for_provider(current_provider)
        info = PROVIDERS[current_provider]

        table = Table(
            title=f"Models — {info.name} ({info.brand})",
            border_style="#d4a574",
            box=box.ROUNDED,
        )
        table.add_column("#", style="bold", width=3)
        table.add_column("Alias", style="cyan")
        table.add_column("Model", style="white")
        table.add_column("Tier", width=6)
        table.add_column("Description", style="dim")

        for i, m in enumerate(models, 1):
            tier = "[green]Free[/green]" if m.is_free else "[yellow]Paid[/yellow]"
            marker = " <" if m.alias == current_alias else ""
            table.add_row(str(i), m.alias, m.model_string, tier, m.description + marker)

        # Render table to string
        with console.capture() as capture:
            console.print(table)
        return CommandResult(output=capture.get())

    # ── /clear ──────────────────────────────────────────────────────────
    if name == "/clear":
        # Clear screen
        os.system("cls" if os.name == "nt" else "clear")
        return CommandResult(
            output="[dim]  Context and screen cleared.[/dim]",
            clear_history=True,
        )

    # ── /tokens ─────────────────────────────────────────────────────────
    if name == "/tokens":
        total_chars = sum(len(m.content) for m in history)
        estimated = total_chars // 4
        limit = config.max_context_tokens
        pct = (100 * estimated // limit) if limit > 0 else 0
        bar_filled = int(pct / 5)
        bar = "[green]" + "█" * bar_filled + "[/green]" + "[dim]░[/dim]" * (20 - bar_filled)
        return CommandResult(
            output=f"\n  {bar} [cyan]~{estimated:,} / {limit:,} tokens ({pct}%)[/cyan]\n"
        )

    # ── /status ─────────────────────────────────────────────────────────
    if name == "/status":
        lines = ["\n[bold]  Provider Status:[/bold]\n"]
        for key in PROVIDER_ORDER:
            info = PROVIDERS[key]
            has_key = get_api_key(key) is not None
            if has_key:
                lines.append(f"    [green]●[/green] {info.name} ({info.brand}) — [green]Connected[/green]")
            else:
                lines.append(f"    [dim]○[/dim] {info.name} ({info.brand}) — [dim]Not configured[/dim]")
        lines.append("")
        return CommandResult(output="\n".join(lines))

    # ── /history ────────────────────────────────────────────────────────
    if name == "/history":
        sessions = session_manager.recent_sessions()
        if not sessions:
            return CommandResult(output="[dim]  No sessions found.[/dim]")

        table = Table(
            title="Recent Sessions",
            border_style="#d4a574",
            box=box.ROUNDED,
        )
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Model", style="yellow")
        table.add_column("Last Updated", style="dim")

        for s in sessions:
            table.add_row(s["id"], s["title"], s["model"], s["updated"][:16])

        with console.capture() as capture:
            console.print(table)
        return CommandResult(output=capture.get())

    # ── /load [session_id] ──────────────────────────────────────────────
    if name == "/load":
        if not arg:
            return CommandResult(output="[red]  Usage: /load <session_id>[/red]", error=True)
        try:
            messages = session_manager.load(arg)
            history.clear()
            history.extend(messages)
            return CommandResult(
                output=f"[green]  >> Loaded session {arg} ({len(messages)} messages).[/green]"
            )
        except Exception as e:
            return CommandResult(output=f"[red]  Failed to load: {e}[/red]", error=True)

    # ── /export ─────────────────────────────────────────────────────────
    if name == "/export":
        if not history:
            return CommandResult(output="[yellow]  Nothing to export.[/yellow]")
        path = session_manager.export_markdown(
            history, export_dir=config.export_dir
        )
        return CommandResult(output=f"[green]  >> Exported to {path}[/green]")

    # ── /attach [path] ──────────────────────────────────────────────────
    if name == "/attach":
        if not arg:
            return CommandResult(output="[red]  Usage: /attach <path>[/red]", error=True)
        try:
            from files.handler import load_file
            attachment = load_file(arg)
            attached_files.append(attachment)
            return CommandResult(
                output=f"[green]  >> Attached: {attachment.name} ({attachment.mime_type})[/green]"
            )
        except (FileNotFoundError, ValueError) as e:
            return CommandResult(output=f"[red]  {e}[/red]", error=True)

    # ── /read [path] ────────────────────────────────────────────────────
    if name == "/read":
        if not arg:
            return CommandResult(output="[red]  Usage: /read <path>[/red]", error=True)
        try:
            p = Path(arg).expanduser().resolve()
            if not p.exists():
                return CommandResult(output=f"[red]  File not found: {arg}[/red]", error=True)
            if not p.is_file():
                return CommandResult(output=f"[red]  Not a file: {arg}[/red]", error=True)

            content = p.read_text(encoding="utf-8", errors="replace")
            # Truncate very large files
            if len(content) > 50000:
                content = content[:50000] + "\n\n... [truncated — file too large]"

            # Add as a user message with the file content
            file_msg = f"[File: {p.name}]\n```\n{content}\n```"
            history.append(Message(role="user", content=file_msg))
            session_manager.save_turn("user", file_msg)

            lines = content.count("\n") + 1
            return CommandResult(
                output=f"[green]  >> Read {p.name} ({lines} lines) — added to context.[/green]"
            )
        except Exception as e:
            return CommandResult(output=f"[red]  Error reading file: {e}[/red]", error=True)

    # ── /run [command] ──────────────────────────────────────────────────
    if name == "/run":
        if not arg:
            return CommandResult(output="[red]  Usage: /run <command>[/red]", error=True)
        try:
            console.print(f"[dim]  $ {arg}[/dim]")
            result = subprocess.run(
                arg,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=os.getcwd(),
            )
            output_text = result.stdout
            if result.stderr:
                output_text += "\n" + result.stderr

            output_text = output_text.strip()
            if not output_text:
                output_text = "(no output)"

            # Truncate very long output
            if len(output_text) > 20000:
                output_text = output_text[:20000] + "\n\n... [truncated]"

            # Show the output to the user
            console.print(f"[dim]{output_text}[/dim]")

            # Add to context
            cmd_msg = f"[Command: `{arg}`]\nExit code: {result.returncode}\n```\n{output_text}\n```"
            history.append(Message(role="user", content=cmd_msg))
            session_manager.save_turn("user", cmd_msg)

            status = "[green]OK[/green]" if result.returncode == 0 else f"[yellow]exit {result.returncode}[/yellow]"
            return CommandResult(
                output=f"\n  {status} Command output added to context.\n"
            )
        except subprocess.TimeoutExpired:
            return CommandResult(
                output="[yellow]  ! Command timed out (30s limit).[/yellow]",
                error=True,
            )
        except Exception as e:
            return CommandResult(output=f"[red]  Error: {e}[/red]", error=True)

    # ── /config ─────────────────────────────────────────────────────────
    if name == "/config":
        from config.loader import get_config_path, ensure_elio_dir
        ensure_elio_dir()
        path = get_config_path()

        if not path.exists():
            from config.loader import load_config
            load_config()

        console.print(f"[dim]  Config: {path}[/dim]")

        if platform.system() == "Windows":
            os.startfile(str(path))
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            editor = os.environ.get("EDITOR", "nano")
            subprocess.run([editor, str(path)])

        return CommandResult(output="[green]  >> Config file opened.[/green]")

    # ── Unknown command ─────────────────────────────────────────────────
    return CommandResult(
        output=f"[red]  Unknown command: {name}. Type /help for commands.[/red]",
        error=True,
    )
