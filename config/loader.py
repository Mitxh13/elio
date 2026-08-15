import logging
from pathlib import Path
import toml
from config.schema import ElioConfig

# The ~/.elio/ directory holds everything: config, history db, logs
ELIO_DIR = Path.home() / ".elio"
CONFIG_PATH = ELIO_DIR / "config.toml"


def ensure_elio_dir():
    """Create ~/.elio/ and sub-folders if they don't exist yet."""
    ELIO_DIR.mkdir(exist_ok=True)
    (ELIO_DIR / "logs").mkdir(exist_ok=True)


def load_config() -> ElioConfig:
    """
    Load config from ~/.elio/config.toml.
    If the file doesn't exist, create it with all defaults.
    """
    ensure_elio_dir()

    if not CONFIG_PATH.exists():
        # First run — write defaults to disk so the user can edit them
        save_config(ElioConfig())

    raw = toml.load(CONFIG_PATH)
    return ElioConfig(**raw)


def save_config(config: ElioConfig):
    """Write the config object back to disk."""
    ensure_elio_dir()
    with open(CONFIG_PATH, "w") as f:
        toml.dump(config.model_dump(), f)


def get_config_path() -> Path:
    return CONFIG_PATH


def setup_logging(level: str = "INFO"):
    """Configure logging to write to ~/.elio/logs/elio.log."""
    ensure_elio_dir()
    log_file = ELIO_DIR / "logs" / "elio.log"
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_file), encoding="utf-8"),
        ],
    )