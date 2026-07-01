import os
from pathlib import Path

import yaml


_project_root = Path(__file__).resolve().parent.parent.parent


def _load_env() -> dict[str, str]:
    """Load .env file as key=value pairs. Returns dict."""
    env = {}
    env_path = _project_root / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    env[key.strip()] = value.strip()
    return env


def load_config(config_path: str | None = None) -> dict:
    """Load YAML config, with .env overrides and path resolution."""
    if config_path is None:
        config_path = _project_root / "config" / "default.yaml"
    else:
        p = Path(config_path)
        if not p.is_absolute():
            config_path = _project_root / p
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Override LLM settings from .env
    env = _load_env()
    if "llm" in cfg:
        if env.get("LLM_API_BASE"):
            cfg["llm"]["api_base"] = env["LLM_API_BASE"]
        if env.get("LLM_API_KEY"):
            cfg["llm"]["api_key"] = env["LLM_API_KEY"]
        if env.get("LLM_MODEL"):
            cfg["llm"]["model"] = env["LLM_MODEL"]

    # Also check OS environment variables (take precedence over .env)
    if "llm" in cfg:
        if os.environ.get("LLM_API_BASE"):
            cfg["llm"]["api_base"] = os.environ["LLM_API_BASE"]
        if os.environ.get("LLM_API_KEY"):
            cfg["llm"]["api_key"] = os.environ["LLM_API_KEY"]
        if os.environ.get("LLM_MODEL"):
            cfg["llm"]["model"] = os.environ["LLM_MODEL"]

    # Resolve relative paths in config
    cfg["_project_root"] = str(_project_root)
    if "asr" in cfg and "hotword_file" in cfg["asr"]:
        hp = Path(cfg["asr"]["hotword_file"])
        if not hp.is_absolute():
            cfg["asr"]["hotword_file"] = str(_project_root / hp)
    if "safety" in cfg and "keywords_file" in cfg["safety"]:
        sp = Path(cfg["safety"]["keywords_file"])
        if not sp.is_absolute():
            cfg["safety"]["keywords_file"] = str(_project_root / sp)
    return cfg
