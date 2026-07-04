"""
Elio Model Registry — single source of truth for all providers and models.
Free providers (Groq, Google) come first.
"""

from dataclasses import dataclass
from providers.base import BaseProvider


@dataclass
class ModelEntry:
    alias:         str   # internal key       e.g. "llama-3.3-70b"
    display_name:  str   # shown to user       e.g. "Llama 3.3 70B"
    model_string:  str   # sent to API         e.g. "llama-3.3-70b-versatile"
    provider_name: str   # "groq" | "google" | "anthropic" | "openai"
    description:   str   # short blurb
    is_free:       bool = False


@dataclass
class ProviderInfo:
    key:      str    # "groq" | "google" | "anthropic" | "openai"
    name:     str    # "Groq"
    brand:    str    # "Llama / Mistral"
    has_free: bool   # whether free tier exists
    login_method: str  # "api_key" | "oauth_or_key" | "api_key_paid"


# ── Provider metadata ────────────────────────────────────────────────────────

PROVIDERS: dict[str, ProviderInfo] = {
    "groq": ProviderInfo(
        key="groq", name="Groq", brand="Llama / Mistral / Gemma", # Fixed brand string
        has_free=True, login_method="api_key",
    ),
    "google": ProviderInfo(
        key="google", name="Google", brand="Gemini",
        has_free=True, login_method="oauth_or_key",
    ),
    "anthropic": ProviderInfo(
        key="anthropic", name="Anthropic", brand="Claude",
        has_free=False, login_method="api_key_paid",
    ),
    "openai": ProviderInfo(
        key="openai", name="OpenAI", brand="GPT",
        has_free=False, login_method="api_key_paid",
    ),
}

# Free providers first
PROVIDER_ORDER = ["groq", "google", "anthropic", "openai"]

# ── Model registry ───────────────────────────────────────────────────────────

MODEL_REGISTRY: dict[str, ModelEntry] = {

# ─── Groq (FREE — Llama, Mistral, Gemma) ─────────────────────────────
    "llama-3.3-70b": ModelEntry(
        alias="llama-3.3-70b",
        display_name="Llama 3.3 70B",
        model_string="llama-3.3-70b-versatile",
        provider_name="groq",
        description="Best free model — smart & fast",
        is_free=True,
    ),
    "llama-3.1-8b": ModelEntry(
        alias="llama-3.1-8b",
        display_name="Llama 3.1 8B",
        model_string="llama-3.1-8b-instant", # The exact valid string Groq expects
        provider_name="groq",
        description="Ultra-fast, lightweight",
        is_free=True,
    ),

# ─── Google Gemini (FREE via AI Studio) ──────────────────────────────
    "gemini-fast": ModelEntry(
        alias="gemini-fast",
        display_name="Gemini 2.5 Flash",
        model_string="gemini-2.5-flash",
        provider_name="google",
        description="Fast & free — great for quick questions",
        is_free=True,
    ),
    "gemini-thinking": ModelEntry(
        alias="gemini-thinking",
        display_name="Gemini 2.5 Pro (Thinking)",
        model_string="gemini-2.5-pro",
        provider_name="google",
        description="Deep reasoning with extended thinking",
        is_free=True,
    ),
    "gemini-pro": ModelEntry(
        alias="gemini-pro",
        display_name="Gemini 2.5 Pro",
        model_string="gemini-2.5-pro",
        provider_name="google",
        description="Most capable — complex reasoning & math",
        is_free=True,
    ),

    # ─── Anthropic Claude (PAID) ──────────────────────────────────────────
    "claude-sonnet": ModelEntry(
        alias="claude-sonnet",
        display_name="Claude Sonnet 5",
        model_string="claude-sonnet-5",
        provider_name="anthropic",
        description="Best for coding & reasoning",
        is_free=False,
    ),
    "claude-opus": ModelEntry(
        alias="claude-opus",
        display_name="Claude Opus 4.8",
        model_string="claude-opus-4-8",
        provider_name="anthropic",
        description="Most capable — complex agentic tasks",
        is_free=False,
    ),
    "claude-haiku": ModelEntry(
        alias="claude-haiku",
        display_name="Claude Haiku 4.5",
        model_string="claude-haiku-4-5-20251001",
        provider_name="anthropic",
        description="Fast & affordable",
        is_free=False,
    ),

    # ─── OpenAI GPT (PAID) ───────────────────────────────────────────────
    "gpt-4o-mini": ModelEntry(
        alias="gpt-4o-mini",
        display_name="GPT-4o Mini",
        model_string="gpt-4o-mini",
        provider_name="openai",
        description="Fast & cheap",
        is_free=False,
    ),
    "gpt-4o": ModelEntry(
        alias="gpt-4o",
        display_name="GPT-4o",
        model_string="gpt-4o",
        provider_name="openai",
        description="Multi-modal, writing & creativity",
        is_free=False,
    ),
    "gpt-4.1": ModelEntry(
        alias="gpt-4.1",
        display_name="GPT-4.1",
        model_string="gpt-4.1",
        provider_name="openai",
        description="Latest & most capable",
        is_free=False,
    ),
    "gpt-4.1-mini": ModelEntry(
        alias="gpt-4.1-mini",
        display_name="GPT-4.1 Mini",
        model_string="gpt-4.1-mini",
        provider_name="openai",
        description="Fast latest-gen",
        is_free=False,
    ),
    "gpt-4.1-nano": ModelEntry(
        alias="gpt-4.1-nano",
        display_name="GPT-4.1 Nano",
        model_string="gpt-4.1-nano",
        provider_name="openai",
        description="Ultra-fast, cheapest",
        is_free=False,
    ),
}

# ── Models grouped by provider ───────────────────────────────────────────────

PROVIDER_MODELS: dict[str, list[str]] = {
    "groq":      ["llama-3.3-70b", "llama-3.1-8b"],
    "google":    ["gemini-fast", "gemini-thinking", "gemini-pro"],
    "anthropic": ["claude-sonnet", "claude-opus", "claude-haiku"],
    "openai":    ["gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"],
}


def resolve_model(alias: str) -> ModelEntry:
    if alias not in MODEL_REGISTRY:
        valid = ", ".join(MODEL_REGISTRY.keys())
        raise KeyError(f"Unknown model '{alias}'. Valid: {valid}")
    return MODEL_REGISTRY[alias]


def get_provider(alias: str) -> BaseProvider:
    entry = resolve_model(alias)

    if entry.provider_name == "groq":
        from providers.groq_provider import GroqProvider
        return GroqProvider()

    if entry.provider_name == "anthropic":
        from providers.claude import ClaudeProvider
        return ClaudeProvider()

    if entry.provider_name == "openai":
        from providers.openai import OpenAIProvider
        return OpenAIProvider()

    if entry.provider_name == "google":
        from providers.gemini import GeminiProvider
        return GeminiProvider()

    raise ValueError(f"No provider class for '{entry.provider_name}'")


def get_models_for_provider(provider_key: str) -> list[ModelEntry]:
    aliases = PROVIDER_MODELS.get(provider_key, [])
    return [MODEL_REGISTRY[a] for a in aliases]


def get_default_model_for_provider(provider_key: str) -> ModelEntry:
    aliases = PROVIDER_MODELS.get(provider_key, [])
    if not aliases:
        raise ValueError(f"No models for provider '{provider_key}'")
    return MODEL_REGISTRY[aliases[0]]
