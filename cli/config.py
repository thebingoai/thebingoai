import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

CONFIG_DIR = Path.home() / ".mdcli"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

@dataclass
class Config:
    backend_url: str = "http://localhost:8000"
    webhook_url: Optional[str] = None
    default_provider: str = "openai"
    default_namespace: str = "default"

def _ensure_config_dir():
    """Ensure config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def get_config() -> Config:
    """Load configuration from file."""
    _ensure_config_dir()

    if CONFIG_FILE.exists():
        try:
            data = yaml.safe_load(CONFIG_FILE.read_text()) or {}
            return Config(
                backend_url=data.get("backend_url", "http://localhost:8000"),
                webhook_url=data.get("webhook_url"),
                default_provider=data.get("default_provider", "openai"),
                default_namespace=data.get("default_namespace", "default")
            )
        except Exception:
            pass

    return Config()

def save_config(config: Config) -> None:
    """Save configuration to file."""
    _ensure_config_dir()

    data = {
        "backend_url": config.backend_url,
        "default_provider": config.default_provider,
        "default_namespace": config.default_namespace
    }
    if config.webhook_url:
        data["webhook_url"] = config.webhook_url

    CONFIG_FILE.write_text(yaml.dump(data, default_flow_style=False))

def set_config_value(key: str, value: str) -> None:
    """Set a single config value."""
    config = get_config()

    if key == "backend_url":
        config.backend_url = value
    elif key == "webhook_url":
        config.webhook_url = value
    elif key == "default_provider":
        config.default_provider = value
    elif key == "default_namespace":
        config.default_namespace = value
    else:
        raise ValueError(f"Unknown config key: {key}")

    save_config(config)
