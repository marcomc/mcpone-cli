from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

from .models import AddedApp, AddedServer

SERVER_ID_PATTERN = re.compile(r"\[id=([A-Z0-9]{6})\]$")
SANITIZED_ID_PATTERN = re.compile(r"_id_([A-Z0-9]{6})$")


def load_config_map(path: Path, key: str) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    if path.suffix.lower() == ".toml":
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    else:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

    mapping = data.get(key, {})
    return mapping if isinstance(mapping, dict) else {}


def write_config_map(path: Path, key: str, value: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        if path.suffix.lower() == ".toml":
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        else:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
    else:
        data = {}

    data[key] = value

    if path.suffix.lower() == ".toml":
        with path.open("wb") as handle:
            tomli_w.dump(data, handle)
    else:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")


def infer_key_style(app: AddedApp) -> str:
    config_path = (app.config_path or "").lower()
    config_key = app.config_key or ""
    if config_key == "mcp_servers":
        return "sanitized"
    if config_path.endswith("mcp-config.json") or config_path.endswith("/mcp.json"):
        return "sanitized"
    return "bracketed"


def slugify_name(name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", name.strip())
    return normalized.strip("_") or "server"


def build_server_key(server_name: str, server_id: str, style: str) -> str:
    if style == "sanitized":
        return f"{slugify_name(server_name)}_id_{server_id}"
    return f"{server_name}[id={server_id}]"


def parse_server_key(raw: str) -> tuple[str, str | None]:
    bracket_match = SERVER_ID_PATTERN.search(raw)
    if bracket_match:
        return raw[: bracket_match.start()], bracket_match.group(1)

    sanitized_match = SANITIZED_ID_PATTERN.search(raw)
    if sanitized_match:
        name = raw[: sanitized_match.start()]
        return name.replace("_", " "), sanitized_match.group(1)

    return raw, None


def server_to_config_dict(server: AddedServer) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if server.command:
        data["command"] = server.command
    if server.args:
        data["args"] = server.args
    if server.env:
        data["env"] = server.env
    if server.url:
        data["url"] = server.url
    if server.headers:
        data["headers"] = server.headers
    return data


def enabled_servers_to_config(
    app: AddedApp,
    servers: list[AddedServer],
) -> dict[str, dict[str, Any]]:
    style = infer_key_style(app)
    return {
        build_server_key(server.name, server.server_id, style): server_to_config_dict(server)
        for server in sorted(servers, key=lambda item: item.name.lower())
    }
