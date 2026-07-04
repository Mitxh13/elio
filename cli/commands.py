import os
import sys
import platform
import subprocess

# Fix Windows console encoding
if sys.platform == "win32":
    os.system("")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich import box

from auth.manager import (
    set_api_key, get_api_key, delete_api_key,
    get_connected_providers, logout_all, PROVIDERS,
)

console = Console()

CURRENT_VERSION = "0.3.0"
GITHUB_API      = "https://api.github.com/repos/Elio-labs/elio/releases/latest"
GITHUB_REPO     = "https://github.com/Elio-labs/elio.git"


# ──────────────────────────────────────────────
# run_login — interactive key entry
# ──────────────────────────────────────────────

def run_login(provider: str | None = None):
    """Prompt the user to add API keys."""
    if provider:
        if provider not in PROVIDERS:
            console.print(f"[red]Unknown provider '{provider}'. Must be one of {PROVIDERS}[/red]")
            return
        providers_to_add = [provider]
    else:
        providers_to_add = PROVIDERS

    console.print()
    console.print("[bold #d4a574]Elio — API Key Setup[/bold #d4a574]")
    console.print("[dim]Keys are stored securely in your OS keyring (never in plain text).[/dim]")
    console.print()

    provider_help = {
        "anthropic": ("console.anthropic.com",  "Settings → API Keys",          "sk-ant-"),
        "google":    ("aistudio.google.com",     "Get API Key → Create API Key", "AIza"),
        "openai":    ("platform.openai.com",     "Profile → API Keys",           "sk-"),
        "groq":      ("console.groq.com",        "API Keys → Create API Key",    "gsk_"),
    }

    for p in providers_to_add:
        existing = get_api_key(p)
        status   = "[green]●[/green]" if existing else "[dim]○[/dim]"
        url, path, prefix = provider_help.get(p, ("", "", ""))

        console.print(f"  {status} [bold]{p.capitalize()}[/bold]")
        if url:
            console.print(f"     [dim]Get key at: {url}  ({path})[/dim]")
            console.print(f"     [dim]Key starts with: {prefix}...[/dim]")

        import getpass
        try:
            if existing:
                raw = getpass.getpass(f"     New key (Enter to keep existing): ")
            else:
                raw = getpass.getpass(f"     Paste API key (Enter to skip): ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n  [dim]Skipped.[/dim]")
            continue

        key = raw.strip()
        if key:
            set_api_key(p, key)
            console.print(f"     [green]✓ Saved.[/green]")
        elif existing:
            console.print(f"     [dim]Kept existing key.[/dim]")
        else:
            console.print(f"     [dim]Skipped.[/dim]")

        console.print()

    console.print("[bold green]Done![/bold green] Run [bold cyan]elio[/bold cyan] to start chatting.\n")


# ──────────────────────────────────────────────
# run_logout
# ──────────────────────────────────────────────

def run_logout():
    """Remove all stored API keys."""
    logout_all()
    console.print("[green]✓ All credentials removed.[/green]")


# ──────────────────────────────────────────────
# run_status
# ──────────────────────────────────────────────

def run_status():
    """Show which providers are configured."""
    from providers.registry import PROVIDERS as PROV_INFO, PROVIDER_ORDER

    table = Table(
        title="Provider Status",
        border_style="#d4a574",
        box=box.ROUNDED,
    )
    table.add_column("Provider", style="cyan")
    table.add_column("Brand",    style="white")
    table.add_column("Status")
    table.add_column("Free Tier")

    for key in PROVIDER_ORDER:
        info    = PROV_INFO[key]
        has_key = get_api_key(key) is not None
        status  = "[green]● Connected[/green]"   if has_key else "[dim]○ Not configured[/dim]"
        free    = "[green]Yes[/green]"            if info.has_free else "[dim]No[/dim]"
        table.add_row(info.name, info.brand, status, free)

    console.print(table)
    console.print("\n  [dim]Run [bold cyan]elio login[/bold cyan] to add missing keys.[/dim]\n")


# ──────────────────────────────────────────────
# run_models
# ──────────────────────────────────────────────

def run_models():
    """List all available models across all providers."""
    from providers.registry import (
        MODEL_REGISTRY, PROVIDER_ORDER, PROVIDER_MODELS, PROVIDERS as PROV_INFO,
    )

    for provider_key in PROVIDER_ORDER:
        info    = PROV_INFO[provider_key]
        aliases = PROVIDER_MODELS.get(provider_key, [])

        table = Table(
            title=f"{info.name} ({info.brand})",
            border_style="#d4a574",
            box=box.ROUNDED,
        )
        table.add_column("Alias",       style="cyan bold")
        table.add_column("Model ID",    style="white")
        table.add_column("Tier",        width=6)
        table.add_column("Description", style="dim")

        for alias in aliases:
            entry = MODEL_REGISTRY[alias]
            tier  = "[green]Free[/green]" if entry.is_free else "[yellow]Paid[/yellow]"
            table.add_row(entry.alias, entry.model_string, tier, entry.description)

        console.print(table)
        console.print()


# ──────────────────────────────────────────────
# run_history
# ──────────────────────────────────────────────

def run_history():
    """Show recent chat sessions."""
    from session.history import init_db, list_sessions

    init_db()
    sessions = list_sessions()
    if not sessions:
        console.print("[dim]No saved sessions yet.[/dim]")
        return

    table = Table(
        title="Recent Sessions",
        border_style="#d4a574",
        box=box.ROUNDED,
    )
    table.add_column("ID",           style="cyan")
    table.add_column("Title",        style="white")
    table.add_column("Model",        style="yellow")
    table.add_column("Last Updated", style="dim")

    for s in sessions:
        table.add_row(s["id"], s["title"], s["model"], s["updated"][:16])

    console.print(table)


# ──────────────────────────────────────────────
# run_config
# ──────────────────────────────────────────────

def run_config():
    """Open the config file in the user's editor."""
    from config.loader import get_config_path, ensure_elio_dir

    ensure_elio_dir()
    path = get_config_path()

    if not path.exists():
        from config.loader import load_config
        load_config()

    console.print(f"[dim]Config file: {path}[/dim]")

    if platform.system() == "Windows":
        os.startfile(str(path))
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        editor = os.environ.get("EDITOR", "nano")
        subprocess.run([editor, str(path)])


# ──────────────────────────────────────────────
# run_update — check GitHub releases and install
# ──────────────────────────────────────────────

def _parse_version(v: str) -> tuple[int, ...]:
    """
    Convert a version string to a comparable int-tuple.
    "0.10.2" → (0, 10, 2)   "1.0" → (1, 0)
    Falls back to (0,) on any parse error.
    """
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except (ValueError, AttributeError):
        return (0,)


def _get_latest_github_version() -> tuple[str | None, str | None]:
    """
    Fetch the latest release tag from the GitHub API.
    Returns (version_str, tag_name) e.g. ("0.2.7", "v0.2.7"),
    or (None, None) on any failure.
    """
    import urllib.request
    import urllib.error
    import json as _json

    try:
        req = urllib.request.Request(
            GITHUB_API,
            headers={
                "Accept":     "application/vnd.github+json",
                "User-Agent": "elio-cli",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode("utf-8"))

        tag = data.get("tag_name", "").strip()
        if not tag:
            return None, None

        version = tag.lstrip("v")
        return version, tag

    except urllib.error.HTTPError as e:
        if e.code == 404:
            # No releases published yet
            console.print(
                "  [yellow]!  No releases found on GitHub yet.[/yellow]\n"
                "  [dim]The repo may not have published a release tag.[/dim]"
            )
        return None, None
    except Exception:
        return None, None


def run_update():
    """
    Check GitHub releases for a newer version and install it via pip from git.
    No PyPI required — installs directly from the GitHub repo tag.
    """
    from rich.status import Status

    console.print()
    console.print(f"  [bold #d4a574]╭─── Elio Update ───╮[/bold #d4a574]")
    console.print(f"  [bold #d4a574]│[/bold #d4a574]")
    console.print(f"  [bold #d4a574]│[/bold #d4a574]  Current version: [bold]{CURRENT_VERSION}[/bold]")
    console.print(f"  [bold #d4a574]│[/bold #d4a574]")

    # Check with spinner
    with Status("  Checking GitHub for updates...", console=console, spinner="dots") as status:
        latest_version, latest_tag = _get_latest_github_version()

    if latest_version is None:
        console.print(
            f"  [bold #d4a574]│[/bold #d4a574]  [yellow]!  Could not reach GitHub.[/yellow]\n"
            f"  [bold #d4a574]│[/bold #d4a574]  [dim]Check your internet connection.[/dim]\n"
            f"  [bold #d4a574]│[/bold #d4a574]  [dim]Manual: pip install git+{GITHUB_REPO}[/dim]\n"
            f"  [bold #d4a574]╰────────────────────╯[/bold #d4a574]"
        )
        console.print()
        return

    console.print(f"  [bold #d4a574]│[/bold #d4a574]  Latest version:  [bold]{latest_version}[/bold]")
    console.print(f"  [bold #d4a574]│[/bold #d4a574]")

    # ── Proper semantic-version comparison ──────────────────────────────────
    current_t = _parse_version(CURRENT_VERSION)
    latest_t  = _parse_version(latest_version)

    if latest_t <= current_t:
        console.print(f"  [bold #d4a574]│[/bold #d4a574]  [green]✓ You are already on the latest version.[/green]")
        console.print(f"  [bold #d4a574]╰────────────────────╯[/bold #d4a574]")
        console.print()
        return

    # ── New version available — install it ──────────────────────────────
    install_url = f"git+{GITHUB_REPO}@{latest_tag}"

    console.print(
        f"  [bold #d4a574]│[/bold #d4a574]  [bold green]New version available: "
        f"{CURRENT_VERSION} → {latest_version}[/bold green]\n"
        f"  [bold #d4a574]│[/bold #d4a574]  [dim]Source: {install_url}[/dim]\n"
        f"  [bold #d4a574]│[/bold #d4a574]"
    )

    console.print(f"  [bold #d4a574]│[/bold #d4a574]  [dim]Installing via pip...[/dim]")

    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", "--upgrade", install_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,   # merge stderr into stdout
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip()
            if line:
                console.print(f"  [bold #d4a574]│[/bold #d4a574]  [dim]{line}[/dim]", highlight=False)

        process.wait()

        console.print(f"  [bold #d4a574]│[/bold #d4a574]")

        if process.returncode == 0:
            console.print(
                f"  [bold #d4a574]│[/bold #d4a574]  [bold green]✓ Elio updated to v{latest_version} successfully![/bold green]\n"
                f"  [bold #d4a574]│[/bold #d4a574]  [dim]Restart your terminal for the update to take effect.[/dim]"
            )
        else:
            console.print(
                f"  [bold #d4a574]│[/bold #d4a574]  [red]pip exited with code {process.returncode}.[/red]\n"
                f"  [bold #d4a574]│[/bold #d4a574]  [dim]Try manually: pip install git+{GITHUB_REPO}[/dim]"
            )

    except FileNotFoundError:
        console.print(
            f"  [bold #d4a574]│[/bold #d4a574]  [red]pip not found. Make sure Python is in your PATH.[/red]\n"
            f"  [bold #d4a574]│[/bold #d4a574]  [dim]Manual: pip install git+{GITHUB_REPO}@{latest_tag}[/dim]"
        )
    except Exception as e:
        console.print(
            f"  [bold #d4a574]│[/bold #d4a574]  [red]Unexpected error: {e}[/red]\n"
            f"  [bold #d4a574]│[/bold #d4a574]  [dim]Manual: pip install git+{GITHUB_REPO}@{latest_tag}[/dim]"
        )

    console.print(f"  [bold #d4a574]╰────────────────────╯[/bold #d4a574]")
    console.print()