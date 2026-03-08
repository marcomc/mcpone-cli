from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w

from .models import AddedApp, AddedServer

SERVER_ID_PATTERN = re.compile(r"\[id=([A-Z0-9]{6})\]$")
SANITIZED_ID_PATTERN = re.compile(r"_id_([A-Z0-9]{6})$")


@dataclass(frozen=True, slots=True)
class SyncProfile:
    key_style: str
    add_tools_wildcard: bool = False
    codex_bearer_token_env: bool = False


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


def infer_sync_profile(app: AddedApp) -> SyncProfile:
    config_path = (app.config_path or "").lower()
    config_key = app.config_key or ""
    app_name = app.name.casefold()
    ai_agent_id = (app.ai_agent_id or "").casefold()
    is_codex = (
        ai_agent_id == "codex"
        or app_name == "codex"
        or config_path.endswith("/.codex/config.toml")
        or config_path.endswith("/config.toml")
        and "/.codex/" in config_path
    )
    if config_path.endswith("mcp-config.json"):
        return SyncProfile(key_style="sanitized", add_tools_wildcard=True)
    if config_path.endswith("/settings.json") and ("gemini" in app_name or ai_agent_id == "gemini"):
        return SyncProfile(key_style="sanitized")
    if config_key == "mcp_servers":
        return SyncProfile(key_style="sanitized", codex_bearer_token_env=is_codex)
    if config_path.endswith("mcp-config.json") or config_path.endswith("/mcp.json"):
        return SyncProfile(key_style="sanitized")
    return SyncProfile(key_style="bracketed")


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


def _codex_bearer_env_var_name(server: AddedServer) -> str:
    if "github" in server.name.casefold():
        return "CODEX_GITHUB_PERSONAL_ACCESS_TOKEN"
    return f"CODEX_{slugify_name(server.name).upper()}_BEARER_TOKEN"


def server_to_config_dict(
    server: AddedServer,
    *,
    add_tools_wildcard: bool = False,
    codex_bearer_token_env: bool = False,
) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if server.command:
        data["command"] = server.command
    if server.args:
        data["args"] = server.args
    if server.env:
        data["env"] = server.env
    if server.url:
        data["url"] = server.url
    headers = dict(server.headers)
    if codex_bearer_token_env and server.url:
        auth_key = next((key for key in headers if key.casefold() == "authorization"), None)
        if auth_key:
            auth_value = str(headers[auth_key]).strip()
            if auth_value.lower().startswith("bearer "):
                data["bearer_token_env_var"] = _codex_bearer_env_var_name(server)
                headers.pop(auth_key)
    if headers:
        data["headers"] = headers
    if add_tools_wildcard:
        data["tools"] = ["*"]
    return data


def enabled_servers_to_config(
    app: AddedApp,
    servers: list[AddedServer],
) -> dict[str, dict[str, Any]]:
    profile = infer_sync_profile(app)
    return {
        build_server_key(server.name, server.server_id, profile.key_style): server_to_config_dict(
            server,
            add_tools_wildcard=profile.add_tools_wildcard,
            codex_bearer_token_env=profile.codex_bearer_token_env,
        )
        for server in sorted(servers, key=lambda item: item.name.lower())
    }
