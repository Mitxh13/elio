"""
Elio CLI — Inline chat interface.
Starts with "Select your AI" — no hardcoded defaults.

Terminal UI inspired by Claude Code:
  ╭─ bordered dashboard with ASCII logo, version info, recent activity ─╮
  │                                                                      │
  ╰──────────────────────────────────────────────────────────────────────╯
"""

import asyncio
import os
import sys
import shutil
from typing import Optional
from datetime import datetime

if sys.platform == "win32":
    os.system("")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.text import Text
from rich.columns import Columns
from rich.align import Align
from rich import box
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from pathlib import Path

from providers.registry import (
    MODEL_REGISTRY, PROVIDERS, PROVIDER_ORDER, PROVIDER_MODELS,
    resolve_model, get_provider, get_models_for_provider,
    get_default_model_for_provider,
)
from providers.base import Message
from config.loader import load_config, save_config
from session.manager import SessionManager
from session.context import truncate_history
from auth.manager import get_api_key, is_provider_ready
from utils.error import friendly_error

console = Console()
VERSION = "0.3.5"

# ── Provider accent colors ───────────────────────────────────────────────────

PROVIDER_COLORS = {
    "groq":      "#ff6b35",   # orange
    "google":    "#4285f4",   # blue
    "anthropic": "#d4a574",   # warm tan (Claude's brand color)
    "openai":    "#10a37f",   # green
}

ACCENT = "#d4a574"   # default warm tan accent (matches Claude Code aesthetic)

PT_STYLE = PTStyle.from_dict({
    "prompt": f"{ACCENT} bold",
    "":       "#93a1a1",
})


# ── Keyboard shortcuts ───────────────────────────────────────────────────────

def create_key_bindings(chat_state: dict):
    """Create prompt_toolkit key bindings for the chat interface.

    NOTE: Ctrl+M is Enter (ASCII 13) and Ctrl+H is Backspace in most terminals.
    We must NEVER bind those or it will break basic input.
    """
    kb = KeyBindings()

    @kb.add('c-p')
    def _(event):
        """Ctrl+P — open model/provider selector."""
        chat_state["pending_command"] = "/provider"
        event.current_buffer.validate_and_handle()

    @kb.add('c-u')
    def _(event):
        """Ctrl+U — attach file prompt."""
        chat_state["pending_command"] = "/attach "
        event.current_buffer.validate_and_handle()

    @kb.add('c-n')
    def _(event):
        """Ctrl+N — new session (clear context)."""
        chat_state["pending_command"] = "/clear"
        event.current_buffer.validate_and_handle()

    @kb.add('c-b')
    def _(event):
        """Ctrl+B — show session history."""
        chat_state["pending_command"] = "/history"
        event.current_buffer.validate_and_handle()

    @kb.add('c-l')
    def _(event):
        """Ctrl+L — clear screen and context."""
        chat_state["pending_command"] = "/clear"
        event.current_buffer.validate_and_handle()

    return kb


# ── ASCII Art ────────────────────────────────────────────────────────────────

MASCOT = """\
[#7878FF] ▄▄▄   ▐▌  ▀   ▄▄▄[/#7878FF]
[#6878FF] █▄▄   ▐▌  █  █▀ ▀█[/#6878FF]
[#5878FF] █▄▄▄  ▐▌  █  ▀█▄█▀[/#5878FF]"""

ELIO_TITLE = "[bold #7878FF]elio[/bold #7878FF]"


# ── Welcome Dashboard ───────────────────────────────────────────────────────

def _get_recent_activity(session_manager: SessionManager | None = None) -> list[str]:
    """Fetch recent session activity for the dashboard."""
    try:
        from session.history import init_db, list_sessions
        init_db()
        sessions = list_sessions(limit=4)
        if not sessions:
            return ["[dim]No recent sessions[/dim]"]

        lines = []
        now = datetime.utcnow()
        for s in sessions:
            try:
                updated = datetime.fromisoformat(s["updated"])
                delta = now - updated
                if delta.days > 7:
                    ago = f"{delta.days // 7}w ago"
                elif delta.days > 0:
                    ago = f"{delta.days}d ago"
                elif delta.seconds > 3600:
                    ago = f"{delta.seconds // 3600}h ago"
                elif delta.seconds > 60:
                    ago = f"{delta.seconds // 60}m ago"
                else:
                    ago = "just now"
            except (ValueError, TypeError):
                ago = "—"

            title = s.get("title", "Untitled")
            if len(title) > 28:
                title = title[:25] + "..."
            lines.append(f"[dim]{ago:<10}[/dim] {title}")

        return lines
    except Exception:
        return ["[dim]No recent sessions[/dim]"]


def _get_connected_status() -> str:
    """Get a quick status line of connected providers."""
    connected = []
    for key in PROVIDER_ORDER:
        if is_provider_ready(key):
            info = PROVIDERS[key]
            connected.append(f"[green]●[/green] {info.name}")
        else:
            info = PROVIDERS[key]
            connected.append(f"[dim]○ {info.name}[/dim]")
    return "  ".join(connected)


def print_welcome_banner():
    """Claude Code-style bordered welcome dashboard."""
    term_width = shutil.get_terminal_size((80, 24)).columns
    panel_width = min(term_width - 4, 76)  # max 76 cols, leave margin

    # ── Left side: mascot + version info ─────────────────────────────────
    cwd = os.getcwd()
    if len(cwd) > 30:
        cwd = "..." + cwd[-27:]

    left_content = (
        f"{MASCOT}\n\n"
        f"  [bold #d4a574]Welcome to Elio[/bold #d4a574]\n\n"
        f"  [dim]v{VERSION} · Unified AI CLI[/dim]\n"
        f"  [dim]{cwd}[/dim]"
    )

    # ── Right side: activity + tips ──────────────────────────────────────
    activity_lines = _get_recent_activity()
    activity_section = f"[bold #d4a574]Recent activity[/bold #d4a574]\n"
    for line in activity_lines:
        activity_section += f"  {line}\n"
    activity_section += f"  [dim]... /history for more[/dim]\n"

    tips_section = (
        f"\n[bold #d4a574]Quick start[/bold #d4a574]\n"
        f"  [cyan]/provider[/cyan]     switch AI model\n"
        f"  [cyan]/attach[/cyan]       attach a file\n"
        f"  [cyan]/read[/cyan]         read file to context\n"
        f"  [dim]... /help for more[/dim]"
    )

    right_content = activity_section + tips_section

    console.print()

    # ── Build the dashboard as a bordered panel ──────────────────────────
    # Use a table to create the two-column layout
    dash_table = Table(
        box=None,
        padding=(0, 2),
        show_header=False,
        show_edge=False,
        expand=True,
    )
    dash_table.add_column(ratio=2, no_wrap=False)
    dash_table.add_column(ratio=3, no_wrap=False)
    dash_table.add_row(left_content, right_content)

    # Wrap in a dashed-border panel
    title_text = f"[bold #d4a574] Elio v{VERSION} [/bold #d4a574]"
    console.print(Panel(
        dash_table,
        title=title_text,
        border_style="#5a5a6e",
        box=box.ROUNDED,
        padding=(1, 2),
        width=panel_width,
    ))
    console.print()


def print_chat_banner(provider_key: str, model_alias: str):
    """Compact model indicator bar shown when entering chat mode."""
    entry = resolve_model(model_alias)
    info  = PROVIDERS[provider_key]
    accent = PROVIDER_COLORS.get(provider_key, ACCENT)
    tier  = "[green]free[/green]" if entry.is_free else "[yellow]paid[/yellow]"

    # Provider status dots
    status_dots = _get_connected_status()

    # Model info line
    model_line = (
        f"[bold {accent}]{info.name}[/bold {accent}] · "
        f"[bold]{entry.display_name}[/bold] · {tier}"
    )

    # Commands hint
    hint_line = "[dim]/help for commands · /provider to switch · /exit to quit[/dim]"

    console.print(Panel(
        f"{model_line}\n{hint_line}",
        border_style=accent,
        box=box.ROUNDED,
        padding=(0, 1),
    ))
    console.print()


# ── Provider / Model Selection ───────────────────────────────────────────────

def _login_label(provider_key: str) -> str:
    """Return a human-readable login method label for a provider."""
    info = PROVIDERS[provider_key]
    if info.login_method == "oauth_or_key":
        return "[green]Free API key (aistudio.google.com)[/green]"
    elif info.login_method == "api_key":
        return "[green]Free API key (console.groq.com)[/green]"
    else:
        return "[yellow]Paid API key required[/yellow]"


def select_ai() -> tuple[str, str] | None:
    """
    'Select your AI' startup screen.
    Returns (provider_key, model_alias) or None if cancelled.
    """
    console.print(Rule(
        "[bold #d4a574]  SELECT YOUR AI  [/bold #d4a574]",
        style="#5a5a6e",
    ))
    console.print()

    # Provider table
    table = Table(
        box=box.SIMPLE_HEAVY,
        padding=(0, 2),
        show_header=True,
        header_style="bold dim",
        border_style="#5a5a6e",
    )
    table.add_column("#",        style="bold #d4a574", width=3,  no_wrap=True)
    table.add_column("Provider", style="bold white",   width=12, no_wrap=True)
    table.add_column("Models",   style="cyan",          width=22, no_wrap=True)
    table.add_column("Access",                          width=38, no_wrap=True)
    table.add_column("",                                width=3,  no_wrap=True)

    brand_models = {
        "groq":      "Llama 3.3, Llama 3.1",
        "google":    "Gemini 2.5 Flash / Pro",
        "anthropic": "Claude Sonnet 5 / Opus / Haiku",
        "openai":    "GPT-5.6 Sol / Terra / Luna",
    }

    for i, key in enumerate(PROVIDER_ORDER, 1):
        info    = PROVIDERS[key]
        ready   = is_provider_ready(key)
        accent  = PROVIDER_COLORS.get(key, ACCENT)
        status  = f"[green]●[/green]" if ready else "[dim]○[/dim]"
        access  = _login_label(key)
        table.add_row(f"{i}.", info.name, brand_models[key], access, status)

    console.print(table)
    console.print()
    console.print("  [dim]● = ready to use    ○ = needs setup[/dim]")
    console.print()

    try:
        raw = input("  Enter 1–4 to select: ").strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if not raw.isdigit() or not (1 <= int(raw) <= len(PROVIDER_ORDER)):
        console.print("[red]  Invalid choice.[/red]")
        return None

    provider_key = PROVIDER_ORDER[int(raw) - 1]

    # Setup if not ready
    if not is_provider_ready(provider_key):
        ok = _setup_provider(provider_key)
        if not ok:
            return None

    # Select model
    console.print()
    alias = select_model(provider_key)
    if not alias:
        return None

    return provider_key, alias


def _setup_provider(provider_key: str) -> bool:
    """
    Guide the user through setting up a provider that isn't configured yet.
    Returns True if setup succeeded.
    """
    info = PROVIDERS[provider_key]
    console.print()

    if provider_key == "groq":
        console.print(f"  [bold]Set up Groq (FREE)[/bold]")
        console.print(f"  [dim]1. Go to: [cyan]console.groq.com[/cyan][/dim]")
        console.print(f"  [dim]2. Sign up (free) → API Keys → Create API Key[/dim]")
        console.print(f"  [dim]3. Paste your key below[/dim]")
        console.print()
        return _prompt_api_key("groq")

    elif provider_key == "google":
        console.print(f"  [bold]Set up Google Gemini[/bold]")
        console.print()
        console.print(f"  [bold #d4a574]1.[/bold #d4a574]  [bold]Sign in with Google[/bold]  [green](recommended — no key needed)[/green]")
        console.print(f"      Opens browser → log in with Google account → done")
        console.print()
        console.print(f"  [bold #d4a574]2.[/bold #d4a574]  [bold]Use a free API key[/bold]")
        console.print(f"      Get it free at: [cyan]aistudio.google.com[/cyan]")
        console.print()
        try:
            choice = input("  Enter 1 or 2: ").strip()
        except (KeyboardInterrupt, EOFError):
            return False

        if choice == "1":
            from auth.oauth import google_login
            return google_login()
        else:
            return _prompt_api_key("google")

    elif provider_key == "anthropic":
        console.print(f"  [bold]Set up Anthropic Claude[/bold]  [yellow](paid — requires credits)[/yellow]")
        console.print(f"  [dim]Get API key at: [cyan]console.anthropic.com[/cyan] → Settings → API Keys[/dim]")
        console.print(f"  [dim]Key starts with: sk-ant-...[/dim]")
        console.print()
        return _prompt_api_key("anthropic")

    elif provider_key == "openai":
        console.print(f"  [bold]Set up OpenAI GPT[/bold]  [yellow](paid — requires credits)[/yellow]")
        console.print(f"  [dim]Get API key at: [cyan]platform.openai.com[/cyan] → API Keys[/dim]")
        console.print(f"  [dim]Key starts with: sk-...[/dim]")
        console.print()
        return _prompt_api_key("openai")

    return False


def _prompt_api_key(provider: str) -> bool:
    """Ask user to paste an API key and save it. Returns True if saved."""
    import getpass
    from auth.manager import set_api_key
    try:
        key = getpass.getpass(f"  Paste API key: ").strip()
    except (KeyboardInterrupt, EOFError):
        return False
    if not key:
        console.print("  [dim]No key entered.[/dim]")
        return False
    set_api_key(provider, key)
    console.print(f"  [green]✓ Key saved.[/green]")
    return True


def select_provider(current_provider: str | None = None) -> str | None:
    """Switch-provider selector (used inside /provider command)."""
    console.print()
    console.print(Rule(
        "[bold #d4a574]  Switch AI Provider  [/bold #d4a574]",
        style="#5a5a6e",
    ))
    console.print()

    for i, key in enumerate(PROVIDER_ORDER, 1):
        info  = PROVIDERS[key]
        ready = is_provider_ready(key)
        accent   = PROVIDER_COLORS.get(key, ACCENT)
        marker   = f"  [cyan]◀ current[/cyan]" if key == current_provider else ""
        status   = "[green]●[/green]" if ready else "[dim]○[/dim]"
        free_tag = "  [green]FREE[/green]" if info.has_free else "  [yellow]PAID[/yellow]"
        console.print(f"    [bold #d4a574]{i}.[/bold #d4a574]  {status} {info.name} ({info.brand}){free_tag}{marker}")

    console.print()
    try:
        raw = input("  Choice [1-4]: ").strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if not raw.isdigit() or not (1 <= int(raw) <= len(PROVIDER_ORDER)):
        return None

    chosen = PROVIDER_ORDER[int(raw) - 1]
    if not is_provider_ready(chosen):
        ok = _setup_provider(chosen)
        if not ok:
            return None
    return chosen


def select_model(provider_key: str, current_alias: str | None = None) -> str | None:
    """Model selector for a given provider."""
    models = get_models_for_provider(provider_key)
    info   = PROVIDERS[provider_key]
    accent = PROVIDER_COLORS.get(provider_key, ACCENT)

    console.print(f"  [bold]Select model — {info.name} ({info.brand}):[/bold]")
    console.print()

    for i, m in enumerate(models, 1):
        tier   = "[green]FREE[/green] " if m.is_free else "[yellow]PAID[/yellow] "
        marker = "  [cyan]◀[/cyan]"     if m.alias == current_alias else ""
        console.print(f"    [bold {accent}]{i:>2}.[/bold {accent}]  {m.display_name:<28} {tier}  [dim]{m.description}[/dim]{marker}")

    console.print()

    default_idx = 1
    for i, m in enumerate(models, 1):
        if m.alias == current_alias:
            default_idx = i
            break

    try:
        raw = input(f"  Choice [1-{len(models)}] (default {default_idx}): ").strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if not raw:
        raw = str(default_idx)

    if not raw.isdigit() or not (1 <= int(raw) <= len(models)):
        console.print("[red]  Invalid choice.[/red]")
        return None

    return models[int(raw) - 1].alias


def full_provider_model_select(
    current_provider: str | None = None,
    current_alias: str | None = None,
) -> tuple[str, str] | None:
    provider = select_provider(current_provider)
    if not provider:
        return None
    alias = select_model(provider, current_alias if current_provider == provider else None)
    if not alias:
        return None
    return provider, alias


# ── Prompt ───────────────────────────────────────────────────────────────────

def make_prompt_text(provider_key: str, model_alias: str) -> HTML:
    entry = resolve_model(model_alias)
    accent = PROVIDER_COLORS.get(provider_key, ACCENT)
    return HTML(
        f'<style fg="{accent}">[{entry.display_name}]</style> '
        f'<style fg="{accent}"><b>❯</b></style> '
    )


# ── Thinking indicator ──────────────────────────────────────────────────────

def _print_thinking_indicator(provider_key: str, model_alias: str):
    """Print a subtle thinking indicator before streaming starts."""
    entry = resolve_model(model_alias)
    accent = PROVIDER_COLORS.get(provider_key, ACCENT)
    console.print(f"\n[bold {accent}]{entry.display_name}:[/bold {accent}] ", end="")


# ── Main entry point ─────────────────────────────────────────────────────────

def run_chat(
    provider_override: str | None = None,
    model_override:    str | None = None,
):
    config = load_config()

    print_welcome_banner()

    if provider_override and model_override:
        current_provider = provider_override
        current_alias    = model_override
    else:
        result = select_ai()
        if not result:
            console.print("\n[dim]No model selected. Exiting.[/dim]\n")
            return
        current_provider, current_alias = result

    os.system("cls" if os.name == "nt" else "clear")
    print_chat_banner(current_provider, current_alias)

    history_path = Path.home() / ".elio" / "prompt_history"
    history_path.parent.mkdir(parents=True, exist_ok=True)

    # Use provider-specific prompt color
    accent = PROVIDER_COLORS.get(current_provider, ACCENT)
    pt_style = PTStyle.from_dict({
        "prompt": f"{accent} bold",
        "":       "#93a1a1",
    })

    pt_session = PromptSession(
        history=FileHistory(str(history_path)),
        style=pt_style,
        multiline=False,
        enable_history_search=True,
    )

    session_manager = SessionManager()
    session_manager.start_new(current_alias)

    chat_state = {"pending_command": None}
    key_bindings = create_key_bindings(chat_state)

    history: list[Message] = []
    attached_files = []

    try:
        asyncio.run(_chat_loop(
            session=pt_session,
            session_manager=session_manager,
            history=history,
            attached_files=attached_files,
            current_provider=current_provider,
            current_alias=current_alias,
            config=config,
            key_bindings=key_bindings,
            chat_state=chat_state,
        ))
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye! [/dim]")
    except EOFError:
        console.print("\n[dim]Goodbye! [/dim]")


async def _chat_loop(
    session, session_manager, history, attached_files,
    current_provider, current_alias, config,
    key_bindings=None, chat_state=None,
):
    from cli.commands_router import route_command

    while True:
        try:
            prompt = make_prompt_text(current_provider, current_alias)

            # Update prompt style when provider changes
            accent = PROVIDER_COLORS.get(current_provider, ACCENT)
            pt_style = PTStyle.from_dict({
                "prompt": f"{accent} bold",
                "":       "#93a1a1",
            })

            text = await session.prompt_async(prompt, style=pt_style, key_bindings=key_bindings)
            text = text.strip()

            # Handle keyboard shortcut commands
            if chat_state and chat_state.get("pending_command"):
                cmd = chat_state.pop("pending_command")
                chat_state["pending_command"] = None
                if cmd == "/attach ":
                    # For attach, prompt for the file path
                    console.print("[cyan]  Enter file path to attach:[/cyan] ", end="")
                    try:
                        attach_path = input().strip()
                        if attach_path:
                            text = f"/attach {attach_path}"
                        else:
                            console.print("[dim]  Cancelled.[/dim]")
                            continue
                    except (KeyboardInterrupt, EOFError):
                        console.print("[dim]  Cancelled.[/dim]")
                        continue
                else:
                    text = cmd

            if not text:
                continue

            if text.startswith("/"):
                result = await route_command(
                    cmd=text,
                    history=history,
                    attached_files=attached_files,
                    current_provider=current_provider,
                    current_alias=current_alias,
                    session_manager=session_manager,
                    config=config,
                )
                if result.output:
                    console.print(result.output)
                if result.new_provider:
                    current_provider = result.new_provider
                if result.new_alias:
                    current_alias = result.new_alias
                    session_manager.start_new(current_alias)
                    print_chat_banner(current_provider, current_alias)
                if result.clear_history:
                    history.clear()
                    attached_files.clear()
                if result.should_exit:
                    console.print("[dim]Goodbye![/dim]")
                    return
                continue

            await _send_message(
                text=text,
                history=history,
                attached_files=attached_files,
                current_alias=current_alias,
                current_provider=current_provider,
                session_manager=session_manager,
                config=config,
            )

        except KeyboardInterrupt:
            console.print()
            continue
        except EOFError:
            console.print("\n[dim]Goodbye![/dim]")
            return


async def _send_message(
    text, history, attached_files, current_alias, current_provider, session_manager, config=None,
):
    entry = resolve_model(current_alias)
    info  = PROVIDERS[current_provider]
    accent = PROVIDER_COLORS.get(current_provider, ACCENT)

    # ── User message ─────────────────────────────────────────────────────
    console.print(f"\n[bold green]You:[/bold green] {text}")
    history.append(Message(role="user", content=text))
    session_manager.save_turn("user", text)

    # ── AI response with thinking indicator ──────────────────────────────
    _print_thinking_indicator(current_provider, current_alias)

    try:
        provider      = get_provider(current_alias)
        full_response = ""
        had_error     = False

        # Truncate history if needed to fit context window
        max_tokens = config.max_context_tokens if config else 8000
        api_messages = truncate_history(history, max_tokens=max_tokens)

        async for token in provider.stream_chat(
            messages=api_messages,
            model=entry.model_string,
            files=attached_files or None,
            alias=current_alias,          # ← needed for thinking config, retry logic
        ):
            # Tokens starting with \n[red] are inline errors from the provider
            # (e.g. rate limit exhausted) — print them but don't save to history
            if token.startswith("\n[red]") or token.startswith("\n⚠️"):
                console.print(token, end="", highlight=False)
                had_error = True
            else:
                console.print(token, end="", highlight=False)
                if not had_error:
                    full_response += token

        console.print("\n")

        if full_response.strip():
            history.append(Message(role="assistant", content=full_response))
            session_manager.save_turn("assistant", full_response)

        attached_files.clear()

    except Exception as e:
        msg = friendly_error(e, current_provider)
        console.print(f"\n{msg}\n")
