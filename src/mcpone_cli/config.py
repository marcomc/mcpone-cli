from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB_PATH = (
    Path.home()
    / "Library/Containers/com.ryankolter9.McpOne/Data/Library/Application Support/McpOne/McpOne.sqlite"
)
DEFAULT_RESOURCES_DIR = Path("/Applications/McpOne.app/Contents/Resources")
DEFAULT_CONFIG_PATH = Path.home() / ".config/mcpone-cli/config.toml"


@dataclass(slots=True)
class Settings:
    db_path: Path = DEFAULT_DB_PATH
    resources_dir: Path = DEFAULT_RESOURCES_DIR
    backup_on_write: bool = True


def _expand_path(value: str | None, fallback: Path) -> Path:
    if not value:
        return fallback
    return Path(value).expanduser()


def load_settings(config_path: Path | None = None) -> Settings:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return Settings()

    with path.open("rb") as handle:
        data = tomllib.load(handle)

    return Settings(
        db_path=_expand_path(data.get("db_path"), DEFAULT_DB_PATH),
        resources_dir=_expand_path(data.get("resources_dir"), DEFAULT_RESOURCES_DIR),
        backup_on_write=bool(data.get("backup_on_write", True)),
    )
